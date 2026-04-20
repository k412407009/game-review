// game-review API 客户端 (Phase 3)
// 默认指向 http://localhost:8787, 可用 NEXT_PUBLIC_API_URL 覆盖。

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8787";

export type JobStage =
  | "queued"
  | "fetching"
  | "scoring"
  | "generating"
  | "packaging"
  | "done"
  | "failed";

export type JobMode = "internal-ppt" | "external-game";

export interface JobProgress {
  stage: JobStage;
  percent: number;
  message: string;
  updated_at: string;
}

export interface JobRequest {
  game_id: string;
  game_name: string;
  mode: JobMode;
  with_visuals: boolean;
  store_url: string | null;
  video_url: string | null;
  notes: string | null;
}

export interface JobRecord {
  job_id: string;
  created_at: string;
  request: JobRequest;
  progress: JobProgress;
  artifacts: string[];
  download_url: string | null;
  error: string | null;
}

export interface CreateJobInput {
  game_id: string;
  game_name: string;
  mode: JobMode;
  with_visuals: boolean;
  store_url?: string;
  video_url?: string;
  notes?: string;
  review_json?: File;
  raw_assets_zip?: File;
}

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, init);
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      msg = body?.detail || body?.message || msg;
    } catch {
      // ignore
    }
    throw new Error(msg);
  }
  return res.json() as Promise<T>;
}

export async function getHealth(): Promise<{ status: string; version: string }> {
  return http("/health");
}

export async function createJob(input: CreateJobInput): Promise<JobRecord> {
  const form = new FormData();
  form.append("game_id", input.game_id);
  form.append("game_name", input.game_name);
  form.append("mode", input.mode);
  form.append("with_visuals", String(input.with_visuals));
  if (input.store_url) form.append("store_url", input.store_url);
  if (input.video_url) form.append("video_url", input.video_url);
  if (input.notes) form.append("notes", input.notes);
  if (input.review_json) form.append("review_json", input.review_json);
  if (input.raw_assets_zip) form.append("raw_assets_zip", input.raw_assets_zip);

  return http("/jobs", {
    method: "POST",
    body: form,
  });
}

export async function getJob(jobId: string): Promise<JobRecord> {
  return http(`/jobs/${jobId}`);
}

export async function listJobs(limit = 50): Promise<JobRecord[]> {
  return http(`/jobs?limit=${limit}`);
}

export function downloadUrl(jobId: string): string {
  return `${API_URL}/jobs/${jobId}/download`;
}

export function artifactUrl(jobId: string, filename: string): string {
  return `${API_URL}/jobs/${jobId}/artifact/${encodeURIComponent(filename)}`;
}

export async function deleteJob(jobId: string): Promise<void> {
  const res = await fetch(`${API_URL}/jobs/${jobId}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`delete failed: ${res.status}`);
}

// 进度条友好的阶段标签
export const STAGE_LABELS: Record<JobStage, string> = {
  queued: "排队中",
  fetching: "1/4 准备素材",
  scoring: "2/4 评审打分",
  generating: "3/4 生成报告",
  packaging: "4/4 打包下载",
  done: "完成",
  failed: "失败",
};

export function isTerminal(stage: JobStage): boolean {
  return stage === "done" || stage === "failed";
}
