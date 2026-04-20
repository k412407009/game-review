"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { listJobs, type JobRecord, STAGE_LABELS } from "@/lib/api";

export default function JobsListPage() {
  const [jobs, setJobs] = useState<JobRecord[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listJobs(50)
      .then(setJobs)
      .catch((e) => setError(e.message));
  }, []);

  if (error) {
    return (
      <div className="card p-6 text-danger-500">
        <strong>加载失败:</strong> {error}
        <div className="mt-2 text-sm text-ink-300">
          API 可能没启动, 跑{" "}
          <code className="font-mono">
            cd apps/api && uvicorn api.main:app --reload --port 8787
          </code>
        </div>
      </div>
    );
  }

  if (jobs === null) {
    return <div className="text-ink-300">加载中…</div>;
  }

  if (jobs.length === 0) {
    return (
      <div className="card p-8 text-center text-ink-300">
        <p>还没有评审记录</p>
        <Link href="/" className="btn btn-primary mt-4 inline-flex">
          提交第一次评审
        </Link>
      </div>
    );
  }

  return (
    <div className="grid gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">历史记录</h1>
        <Link href="/" className="btn btn-secondary">
          新建评审
        </Link>
      </div>

      <div className="card overflow-hidden">
        <table className="w-full">
          <thead className="bg-ink-900/80 text-xs text-ink-400 uppercase tracking-wider">
            <tr>
              <th className="px-4 py-3 text-left">Job ID</th>
              <th className="px-4 py-3 text-left">游戏</th>
              <th className="px-4 py-3 text-left">模式</th>
              <th className="px-4 py-3 text-left">状态</th>
              <th className="px-4 py-3 text-left">时间</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-ink-700">
            {jobs.map((j) => (
              <tr key={j.job_id} className="hover:bg-ink-700/40">
                <td className="px-4 py-3 font-mono text-xs">
                  <Link
                    href={`/jobs/${j.job_id}`}
                    className="text-accent-300 hover:text-accent-400"
                  >
                    {j.job_id}
                  </Link>
                </td>
                <td className="px-4 py-3">
                  <div className="font-medium">{j.request.game_name}</div>
                  <div className="text-xs text-ink-400 font-mono">{j.request.game_id}</div>
                </td>
                <td className="px-4 py-3 text-sm text-ink-300">
                  {j.request.mode === "external-game" ? "外部游戏" : "内部 PPT"}
                </td>
                <td className="px-4 py-3">
                  <StageBadge stage={j.progress.stage} />
                </td>
                <td className="px-4 py-3 text-sm text-ink-400">
                  {new Date(j.created_at).toLocaleString("zh-CN")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function StageBadge({ stage }: { stage: JobRecord["progress"]["stage"] }) {
  const cls =
    stage === "done"
      ? "bg-success-100 text-success-500"
      : stage === "failed"
      ? "bg-danger-100/20 text-danger-500"
      : "bg-accent-300/20 text-accent-300";
  return <span className={`badge ${cls}`}>{STAGE_LABELS[stage]}</span>;
}
