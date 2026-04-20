"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { createJob, type JobMode } from "@/lib/api";

export default function HomePage() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const f = e.currentTarget;
      const data = new FormData(f);
      const reviewFile = (f.elements.namedItem("review_json") as HTMLInputElement).files?.[0];
      const assetsFile = (f.elements.namedItem("raw_assets_zip") as HTMLInputElement).files?.[0];

      const rec = await createJob({
        game_id: String(data.get("game_id") || "").trim(),
        game_name: String(data.get("game_name") || "").trim(),
        mode: (String(data.get("mode")) as JobMode) || "external-game",
        with_visuals: data.get("with_visuals") === "on",
        store_url: String(data.get("store_url") || "").trim() || undefined,
        video_url: String(data.get("video_url") || "").trim() || undefined,
        notes: String(data.get("notes") || "").trim() || undefined,
        review_json: reviewFile,
        raw_assets_zip: assetsFile,
      });
      router.push(`/jobs/${rec.job_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setSubmitting(false);
    }
  }

  return (
    <div className="grid gap-8">
      <section>
        <h1 className="text-3xl font-bold">提交评审任务</h1>
        <p className="text-ink-300 mt-2">
          5 位评委 × 7 个维度, 产出 <strong>Word + Excel + Markdown</strong> 三件套.
          <span className="text-ink-400 ml-2">(Phase 3 MVP · AI 评审当前是 stub, 需接入 LLM)</span>
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
                生成 <strong>视觉索引 Sheet</strong> (需 raw_assets 素材)
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
          <p className="hint">Phase 3 仅作元数据记录, Phase 4 会接入自动抓取</p>
        </div>

        <div>
          <label className="label" htmlFor="video_url">Gameplay 视频 URL (可选)</label>
          <input
            id="video_url"
            name="video_url"
            className="input"
            placeholder="https://youtube.com/watch?v=..."
          />
        </div>

        <div>
          <label className="label" htmlFor="notes">备注 / 上下文 (可选)</label>
          <textarea
            id="notes"
            name="notes"
            rows={3}
            className="input resize-y"
            placeholder="例: 这款游戏是 4X SLG 海洋题材, 重点看 D1 匹配度 + D5 商业化..."
          />
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
              <code className="font-mono">curl http://localhost:8787/health</code>
            </div>
          </div>
        )}

        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={submitting}
            className="btn btn-primary"
          >
            {submitting ? "提交中…" : "开始评审"}
          </button>
          <button type="reset" className="btn btn-ghost">
            重置
          </button>
        </div>
      </form>

      <section className="card p-6 bg-ink-900/60">
        <h2 className="text-lg font-semibold mb-3">流水线阶段</h2>
        <ol className="grid gap-2 text-sm text-ink-200 list-decimal pl-5">
          <li>
            <strong>准备素材</strong>: 解压上传的 raw_assets.zip (如果有)
          </li>
          <li>
            <strong>评审打分</strong>: 用户提供的 review.json OR AI stub (
            <span className="text-warning-500">接 LLM 前是占位</span>)
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
