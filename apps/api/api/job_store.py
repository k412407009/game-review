"""In-memory job store + 文件持久化

Phase 3 用 dict + asyncio.Lock 管 job 状态, 重启即丢。
Phase 4 换成 Postgres/Redis。

每个 job 对应磁盘目录:
  data/jobs/<job_id>/
    request.json        # 用户提交的元数据
    progress.json       # 最新进度 (也在内存)
    input/              # 用户上传的原始文件 (raw_assets.zip, review.json)
    workdir/            # 流水线运行时的展开目录 (给 game-review CLI 消费)
      review/
        <game>_review.json   # 由 ai_stub 或用户上传的
      raw_assets/            # 可选
    output/             # 产出三件套 (docx / xlsx / md) + 打包 zip
"""

from __future__ import annotations

import asyncio
import json
import re
import secrets
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .schemas import JobCreate, JobProgress, JobRecord, JobStage

# 数据根目录; 可用 env 覆盖
import os

DATA_ROOT = Path(os.environ.get("GAME_REVIEW_DATA_ROOT", Path(__file__).resolve().parent.parent / "data"))
JOBS_ROOT = DATA_ROOT / "jobs"
JOBS_ROOT.mkdir(parents=True, exist_ok=True)


_JOBS: dict[str, JobRecord] = {}
_LOCK = asyncio.Lock()

# Job id 格式: YYMMDD-<6char hex>; 简短可读 + 不冲突
_JOB_ID_RE = re.compile(r"^\d{6}-[0-9a-f]{6}$")


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def new_job_id() -> str:
    return f"{_now().strftime('%y%m%d')}-{secrets.token_hex(3)}"


def job_dir(job_id: str) -> Path:
    if not _JOB_ID_RE.match(job_id):
        raise ValueError(f"非法 job_id 格式: {job_id}")
    return JOBS_ROOT / job_id


async def create_job(req: JobCreate) -> JobRecord:
    async with _LOCK:
        jid = new_job_id()
        while jid in _JOBS or job_dir(jid).exists():
            jid = new_job_id()
        d = job_dir(jid)
        (d / "input").mkdir(parents=True, exist_ok=True)
        (d / "workdir").mkdir(parents=True, exist_ok=True)
        (d / "output").mkdir(parents=True, exist_ok=True)

        rec = JobRecord(
            job_id=jid,
            created_at=_now(),
            request=req,
            progress=JobProgress(stage=JobStage.QUEUED, percent=0, message="任务已创建", updated_at=_now()),
        )
        _JOBS[jid] = rec
        _persist(rec)
        return rec


async def get_job(job_id: str) -> JobRecord | None:
    async with _LOCK:
        rec = _JOBS.get(job_id)
        if rec is None:
            # 尝试从磁盘恢复 (服务重启后)
            rec = _load_from_disk(job_id)
            if rec is not None:
                _JOBS[job_id] = rec
        return rec


async def list_jobs(limit: int = 50) -> list[JobRecord]:
    async with _LOCK:
        items = list(_JOBS.values())
    items.sort(key=lambda r: r.created_at, reverse=True)
    return items[:limit]


async def update_progress(
    job_id: str,
    *,
    stage: JobStage | None = None,
    percent: int | None = None,
    message: str | None = None,
    artifacts: list[str] | None = None,
    download_url: str | None = None,
    error: str | None = None,
) -> None:
    async with _LOCK:
        rec = _JOBS.get(job_id)
        if rec is None:
            return
        p = rec.progress
        if stage is not None:
            p.stage = stage
        if percent is not None:
            p.percent = max(0, min(100, percent))
        if message is not None:
            p.message = message
        p.updated_at = _now()
        if artifacts is not None:
            rec.artifacts = artifacts
        if download_url is not None:
            rec.download_url = download_url
        if error is not None:
            rec.error = error
        _persist(rec)


def _persist(rec: JobRecord) -> None:
    d = job_dir(rec.job_id)
    (d / "request.json").write_text(rec.request.model_dump_json(indent=2), encoding="utf-8")
    (d / "progress.json").write_text(rec.progress.model_dump_json(indent=2), encoding="utf-8")
    full_state = rec.model_dump(mode="json")
    (d / "state.json").write_text(json.dumps(full_state, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _load_from_disk(job_id: str) -> JobRecord | None:
    d = job_dir(job_id) if _JOB_ID_RE.match(job_id) else None
    if d is None or not d.exists():
        return None
    state_path = d / "state.json"
    if not state_path.exists():
        return None
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        return JobRecord.model_validate(state)
    except Exception:
        return None


def bootstrap_from_disk() -> int:
    """启动时扫一遍 JOBS_ROOT, 把已有 job 灌入内存.

    返回灌入的 job 数. 在 main.py 的 lifespan startup 调用一次即可.
    设计原因:
        - _JOBS 内存 store 是 source of truth for list_jobs (性能考虑)
        - 服务重启/重新部署后, 不 bootstrap 的话 list_jobs 会假装历史是空的
        - get_job(id) 已有 fallback, 但 list_jobs() 没有 — 所以必须启动 hydrate
    幂等: 已在内存的 job 不覆盖 (避免 race 在中途调用导致丢进度).
    """
    if not JOBS_ROOT.exists():
        return 0
    loaded = 0
    for d in sorted(JOBS_ROOT.iterdir()):
        if not d.is_dir():
            continue
        if not _JOB_ID_RE.match(d.name):
            continue
        if d.name in _JOBS:
            continue
        rec = _load_from_disk(d.name)
        if rec is not None:
            _JOBS[d.name] = rec
            loaded += 1
    return loaded


async def delete_job(job_id: str) -> bool:
    async with _LOCK:
        rec = _JOBS.pop(job_id, None)
        d = job_dir(job_id) if _JOB_ID_RE.match(job_id) else None
        if d and d.exists():
            shutil.rmtree(d, ignore_errors=True)
        return rec is not None
