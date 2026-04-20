"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import {
  API_URL,
  artifactUrl,
  downloadUrl,
  getJob,
  isTerminal,
  type JobRecord,
  STAGE_LABELS,
} from "@/lib/api";

const POLL_INTERVAL_MS = 1500;

export default function JobDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [job, setJob] = useState<JobRecord | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | null = null;

    async function tick() {
      try {
        const j = await getJob(id);
        if (!alive) return;
        setJob(j);
        if (!isTerminal(j.progress.stage)) {
          timer = setTimeout(tick, POLL_INTERVAL_MS);
        }
      } catch (e) {
        if (!alive) return;
        setError(e instanceof Error ? e.message : String(e));
      }
    }
    tick();

    return () => {
      alive = false;
      if (timer) clearTimeout(timer);
    };
  }, [id]);

  if (error) {
    return (
      <div className="card p-6 text-danger-500">
        <strong>加载失败:</strong> {error}
        <div className="mt-4">
          <Link href="/" className="btn btn-secondary">返回</Link>
        </div>
      </div>
    );
  }

  if (!job) {
    return <div className="text-ink-300">加载中…</div>;
  }

  const terminal = isTerminal(job.progress.stage);

  return (
    <div className="grid gap-6">
      <header className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">{job.request.game_name}</h1>
          <p className="text-ink-400 text-sm font-mono mt-1">
            {job.job_id} · {job.request.game_id} · {job.request.mode}
            {job.request.with_visuals ? " · --with-visuals" : ""}
          </p>
        </div>
        <div className="flex gap-2">
          <Link href="/jobs" className="btn btn-ghost text-sm">历史</Link>
          <Link href="/" className="btn btn-secondary text-sm">新建</Link>
        </div>
      </header>

      <ProgressCard job={job} />

      {terminal && job.progress.stage === "done" && <DoneCard job={job} />}

      {job.progress.stage === "failed" && <FailedCard job={job} />}

      <DetailsCard job={job} />
    </div>
  );
}

function ProgressCard({ job }: { job: JobRecord }) {
  const terminal = isTerminal(job.progress.stage);
  const color =
    job.progress.stage === "done"
      ? "bg-success-500"
      : job.progress.stage === "failed"
      ? "bg-danger-500"
      : "bg-accent-500";
  return (
    <div className="card p-6">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm text-ink-300">
          {STAGE_LABELS[job.progress.stage]}
        </span>
        <span className="text-sm font-mono text-ink-200">
          {job.progress.percent}%
        </span>
      </div>
      <div className="w-full h-2 bg-ink-700 rounded-full overflow-hidden">
        <div
          className={`h-full ${color} transition-all duration-300`}
          style={{ width: `${job.progress.percent}%` }}
        />
      </div>
      {!terminal && (
        <p className="text-xs text-ink-400 mt-3">
          自动刷新 (每 {POLL_INTERVAL_MS / 1000}s), 不要关闭这个页面
        </p>
      )}
      <p className="text-sm text-ink-200 mt-3">{job.progress.message}</p>
    </div>
  );
}

function DoneCard({ job }: { job: JobRecord }) {
  const bundle = job.artifacts.find((a) => a.endsWith(".zip"));
  const docs = job.artifacts.filter((a) => !a.endsWith(".zip"));
  return (
    <div className="card p-6 border-success-500/40 bg-success-500/5">
      <div className="flex items-center gap-2 mb-4">
        <span className="inline-block w-2 h-2 bg-success-500 rounded-full"></span>
        <h2 className="text-lg font-semibold text-success-500">评审完成</h2>
      </div>
      <div className="grid gap-3">
        {bundle && (
          <a
            href={downloadUrl(job.job_id)}
            className="btn btn-primary w-fit"
            download
          >
            下载全部 (bundle.zip)
          </a>
        )}
        {docs.length > 0 && (
          <div>
            <p className="text-sm text-ink-300 mb-2">或单独下载:</p>
            <ul className="grid gap-2">
              {docs.map((name) => (
                <li key={name}>
                  <a
                    href={artifactUrl(job.job_id, name)}
                    className="text-accent-300 hover:text-accent-400 text-sm font-mono"
                    download
                  >
                    ↓ {name}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

function FailedCard({ job }: { job: JobRecord }) {
  return (
    <div className="card p-6 border-danger-500/40 bg-danger-500/5">
      <div className="flex items-center gap-2 mb-3">
        <span className="inline-block w-2 h-2 bg-danger-500 rounded-full"></span>
        <h2 className="text-lg font-semibold text-danger-500">评审失败</h2>
      </div>
      {job.error && (
        <pre className="text-xs font-mono bg-ink-900 border border-ink-600 rounded p-3 overflow-x-auto max-h-96 whitespace-pre-wrap">
{job.error}
        </pre>
      )}
      <p className="text-sm text-ink-400 mt-3">
        查服务端日志: 运行 uvicorn 的终端
      </p>
    </div>
  );
}

function DetailsCard({ job }: { job: JobRecord }) {
  return (
    <details className="card p-6">
      <summary className="cursor-pointer select-none font-medium">
        原始请求 + 任务详情
      </summary>
      <dl className="grid md:grid-cols-2 gap-4 mt-4 text-sm">
        <div>
          <dt className="text-ink-400">game_id</dt>
          <dd className="font-mono">{job.request.game_id}</dd>
        </div>
        <div>
          <dt className="text-ink-400">game_name</dt>
          <dd>{job.request.game_name}</dd>
        </div>
        <div>
          <dt className="text-ink-400">mode</dt>
          <dd>{job.request.mode}</dd>
        </div>
        <div>
          <dt className="text-ink-400">with_visuals</dt>
          <dd>{job.request.with_visuals ? "true" : "false"}</dd>
        </div>
        <div className="md:col-span-2">
          <dt className="text-ink-400">store_url</dt>
          <dd className="font-mono break-all">
            {job.request.store_url || <span className="text-ink-500">(未提供)</span>}
          </dd>
        </div>
        <div className="md:col-span-2">
          <dt className="text-ink-400">video_url</dt>
          <dd className="font-mono break-all">
            {job.request.video_url || <span className="text-ink-500">(未提供)</span>}
          </dd>
        </div>
        <div className="md:col-span-2">
          <dt className="text-ink-400">notes</dt>
          <dd className="whitespace-pre-wrap">
            {job.request.notes || <span className="text-ink-500">(无)</span>}
          </dd>
        </div>
        <div>
          <dt className="text-ink-400">created_at</dt>
          <dd className="font-mono">
            {new Date(job.created_at).toLocaleString("zh-CN")}
          </dd>
        </div>
        <div>
          <dt className="text-ink-400">updated_at</dt>
          <dd className="font-mono">
            {new Date(job.progress.updated_at).toLocaleString("zh-CN")}
          </dd>
        </div>
        <div className="md:col-span-2">
          <dt className="text-ink-400">API</dt>
          <dd className="font-mono text-xs">{API_URL}</dd>
        </div>
      </dl>
    </details>
  );
}
