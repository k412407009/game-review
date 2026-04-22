"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import {
  createJob,
  findJobByClientRequestId,
  getHealth,
  type JobMode,
} from "@/lib/api";

const healthUrl =
  process.env.NEXT_PUBLIC_API_URL || "https://api.run.ingarena.net";
const NOTES_MAX_LENGTH = 20000;

export default function HomePage() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function goToJob(jobId: string) {
    if (typeof window !== "undefined") {
      window.location.assign(`/jobs/${jobId}`);
      return;
    }
    router.push(`/jobs/${jobId}`);
  }

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    const clientRequestId =
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : `web-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    try {
      const f = e.currentTarget;
      const data = new FormData(f);
      const reviewFile = (f.elements.namedItem("review_json") as HTMLInputElement).files?.[0];
      const assetsFile = (f.elements.namedItem("raw_assets_zip") as HTMLInputElement).files?.[0];
      const notes = String(data.get("notes") || "").trim();

      if (notes.length > NOTES_MAX_LENGTH) {
        throw new Error(`备注 / 上下文最多 ${NOTES_MAX_LENGTH} 个字符，当前过长，请精简后再提交。`);
      }

      const rec = await createJob({
        game_id: String(data.get("game_id") || "").trim(),
        game_name: String(data.get("game_name") || "").trim(),
        clientRequestId,
        mode: (String(data.get("mode")) as JobMode) || "external-game",
        with_visuals: data.get("with_visuals") === "on",
        store_url: String(data.get("store_url") || "").trim() || undefined,
        video_url: String(data.get("video_url") || "").trim() || undefined,
        reference_url: String(data.get("reference_url") || "").trim() || undefined,
        notes: notes || undefined,
        review_json: reviewFile,
        raw_assets_zip: assetsFile,
      });
      goToJob(rec.job_id);
    } catch (err) {
      let message = err instanceof Error ? err.message : String(err);
      if (message === "Failed to fetch") {
        try {
          const recovered = await findJobByClientRequestId(clientRequestId);
          goToJob(recovered.job_id);
          return;
        } catch {
          // ignore and continue to diagnostics below
        }
        try {
          await getHealth();
          message =
            "页面当前能访问 API，但本次提交请求在浏览器侧失败。常见原因是旧缓存页面或浏览器扩展拦截。请先按 Command + Shift + R 强制刷新后再试。";
        } catch {
          message =
            "无法连接 API。请先确认 https://api.run.ingarena.net/health 能打开，再重试。";
        }
      }
      setError(message);
      setSubmitting(false);
    }
  }

  return (
    <div className="grid gap-8">
      <section>
        <h1 className="text-3xl font-bold">提交评审任务</h1>
        <p className="text-ink-300 mt-2">
          5 位评委 × 7 个维度, 产出 <strong>Word + Excel + Markdown</strong> 三件套.
          <span className="text-ink-400 ml-2">(Phase 3 MVP · 默认走 Compass, 异常时回退 stub)</span>
        </p>
      </section>

      <form onSubmit={handleSubmit} className="grid gap-6 card p-6">
        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <label className="label" htmlFor="game_id">
              项目 id <span className="text-danger-500">*</span>
            </label>
            <input
              id="game_id"
              name="game_id"
              required
              className="input"
              placeholder="last-beacon"
              pattern="[a-zA-Z0-9_\-]{1,64}"
              title="只支持字母数字下划线连字符, 会成为文件名一部分"
            />
            <p className="hint">仅字母/数字/下划线/连字符; 作为文件名前缀</p>
          </div>
          <div>
            <label className="label" htmlFor="game_name">
              游戏名 <span className="text-danger-500">*</span>
            </label>
            <input
              id="game_name"
              name="game_name"
              required
              className="input"
              placeholder="Last Beacon: Survival"
            />
            <p className="hint">用于报告标题, 可含中文/空格/符号</p>
          </div>
        </div>

        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <label className="label" htmlFor="mode">模式</label>
            <select id="mode" name="mode" className="input" defaultValue="external-game">
              <option value="external-game">外部游戏评审 (已上线产品)</option>
              <option value="internal-ppt">内部立项 PPT 评审</option>
            </select>
          </div>
          <div className="flex items-end">
            <label className="flex items-center gap-2 cursor-pointer select-none">
              <input
                type="checkbox"
                name="with_visuals"
                defaultChecked
                className="w-4 h-4 accent-accent-500"
              />
              <span className="text-sm text-ink-200">
                生成 <strong>视觉索引 Sheet</strong> (支持自动抓商店截图 / 视频关键帧，也可手动上传 raw_assets)
              </span>
            </label>
          </div>
        </div>

        <div>
          <label className="label" htmlFor="store_url">商店页 URL (可选)</label>
          <input
            id="store_url"
            name="store_url"
            className="input"
            placeholder="https://play.google.com/store/apps/details?id=..."
          />
          <p className="hint">支持 Google Play / App Store 自动抓商店文案、评分信息和截图。</p>
        </div>

        <div>
          <label className="label" htmlFor="video_url">Gameplay 视频 URL (可选)</label>
          <input
            id="video_url"
            name="video_url"
            className="input"
            placeholder="https://youtube.com/watch?v=..."
          />
          <p className="hint">支持 YouTube 自动抽关键帧，并并入评审上下文与视觉索引。</p>
        </div>

        <div>
          <label className="label" htmlFor="reference_url">参考文章 URL (可选)</label>
          <input
            id="reference_url"
            name="reference_url"
            className="input"
            placeholder="https://mp.weixin.qq.com/s/..."
          />
          <p className="hint">支持微信公众号文章；后端会自动抓正文并并入评审上下文。</p>
        </div>

        <div>
          <label className="label" htmlFor="notes">备注 / 上下文 (可选)</label>
          <textarea
            id="notes"
            name="notes"
            rows={3}
            maxLength={NOTES_MAX_LENGTH}
            className="input resize-y"
            placeholder="例: 这款游戏是 4X SLG 海洋题材, 重点看 D1 匹配度 + D5 商业化；也可直接粘贴 mp.weixin 链接"
          />
          <p className="hint">最多 {NOTES_MAX_LENGTH} 个字符；支持在正文里直接粘贴 mp.weixin 链接。</p>
        </div>

        <details className="border border-ink-600 rounded-lg p-4 bg-ink-900/60">
          <summary className="cursor-pointer select-none font-medium">
            高级: 上传 review.json 或素材 zip (可选)
          </summary>
          <div className="mt-4 grid gap-4">
            <div>
              <label className="label" htmlFor="review_json">
                review.json (跳过 AI 评审, 直接走 CLI)
              </label>
              <input
                id="review_json"
                name="review_json"
                type="file"
                accept=".json,application/json"
                className="input"
              />
              <p className="hint">
                上传后 API 会跳过 AI 评审, 直接用这个 JSON 跑 game-review CLI.
                schema 见{" "}
                <a
                  href="https://github.com/k412407009/game-review/blob/main/skills/game-review/references/review-board.md"
                  target="_blank"
                  rel="noreferrer"
                  className="text-accent-300 underline"
                >
                  review-board.md §VI
                </a>
              </p>
            </div>
            <div>
              <label className="label" htmlFor="raw_assets_zip">
                raw_assets.zip (给 --with-visuals 用)
              </label>
              <input
                id="raw_assets_zip"
                name="raw_assets_zip"
                type="file"
                accept=".zip,application/zip"
                className="input"
              />
              <p className="hint">
                zip 根解压后应有{" "}
                <code className="font-mono">{"<project>/store/"}</code> 和{" "}
                <code className="font-mono">{"<project>/gameplay/frames/"}</code>
              </p>
            </div>
          </div>
        </details>

        {error && (
          <div className="rounded-lg bg-danger-100/10 border border-danger-500/40 text-danger-500 px-4 py-3 text-sm">
            <strong>提交失败:</strong> {error}
            <div className="mt-1 text-ink-300">
              检查 API 是否启动:{" "}
              <code className="font-mono">curl {healthUrl}/health</code>
            </div>
          </div>
        )}

        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={submitting}
          className="btn btn-primary"
        >
            {submitting ? "正在提交…" : "开始评审"}
          </button>
          <button type="reset" className="btn btn-ghost">
            重置
          </button>
        </div>
        {submitting && (
          <p className="text-sm text-ink-400">
            正在把表单提交到 API；只有自动跳转到任务详情页，才算任务创建成功。
          </p>
        )}
      </form>

      <section className="card p-6 bg-ink-900/60">
        <h2 className="text-lg font-semibold mb-3">流水线阶段</h2>
        <ol className="grid gap-2 text-sm text-ink-200 list-decimal pl-5">
          <li>
            <strong>准备素材</strong>: 解压 raw_assets.zip，并自动抓取参考文章正文 (如果提供了 mp.weixin / 文章 URL)
          </li>
          <li>
            <strong>评审打分</strong>: 用户提供的 review.json OR Compass 自动评审 (
            <span className="text-warning-500">上游异常时才回退到占位 stub</span>)
          </li>
          <li>
            <strong>生成报告</strong>: 调 <code className="font-mono">game-review review</code> CLI
          </li>
          <li>
            <strong>打包下载</strong>: 把 docx / xlsx / md 打成 zip
          </li>
        </ol>
      </section>
    </div>
  );
}
