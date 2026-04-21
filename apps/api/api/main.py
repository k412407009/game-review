"""FastAPI app · game-review Web MVP (Phase 3)

启动:
  cd apps/api
  source ../../.venv/bin/activate    # 用 repo 根的 venv (game-review CLI 已装)
  pip install -e .                   # 首次: 装 FastAPI 等后端依赖
  uvicorn api.main:app --reload --port 8787

跨域: 默认允许 http://localhost:3000 (Next.js dev server) + http://127.0.0.1:3000
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from . import __version__
from .job_store import (
    JOBS_ROOT,
    bootstrap_from_disk,
    create_job,
    delete_job,
    get_job,
    job_dir,
    list_jobs,
)
from .pipeline import run_pipeline
from .schemas import JobCreate, JobMode, JobRecord, JobStage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    n = bootstrap_from_disk()
    log.info("bootstrap: 从磁盘恢复 %d 个历史 job (data_root=%s)", n, JOBS_ROOT)
    yield


app = FastAPI(
    title="game-review API",
    description="Phase 3 Web MVP: 单用户 Web UI → CLI pipeline → 下载报告",
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ================= routes =================


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "version": __version__,
        "data_root": str(JOBS_ROOT),
    }


@app.post("/jobs", response_model=JobRecord, status_code=201)
async def create_job_endpoint(
    background_tasks: BackgroundTasks,
    game_id: str = Form(...),
    game_name: str = Form(...),
    mode: JobMode = Form(JobMode.EXTERNAL_GAME),
    with_visuals: bool = Form(True),
    store_url: str | None = Form(None),
    video_url: str | None = Form(None),
    notes: str | None = Form(None),
    review_json: UploadFile | None = File(None),
    raw_assets_zip: UploadFile | None = File(None),
) -> JobRecord:
    """提交评审任务.

    两种用法:
      A. 只填元数据 → API 用 AI stub 生成占位 review.json (Phase 3 默认)
      B. 上传 review.json (+ 可选 raw_assets.zip) → 用用户提供的, 跳过 AI 评审
    """
    req = JobCreate(
        game_id=game_id,
        game_name=game_name,
        mode=mode,
        with_visuals=with_visuals,
        store_url=store_url,
        video_url=video_url,
        notes=notes,
    )
    rec = await create_job(req)

    # 保存上传的文件到 input/
    d = job_dir(rec.job_id)
    if review_json is not None:
        data = await review_json.read()
        (d / "input" / "review.json").write_bytes(data)
    if raw_assets_zip is not None:
        data = await raw_assets_zip.read()
        (d / "input" / "raw_assets.zip").write_bytes(data)

    # 跑 pipeline 作为 background task (不 block 请求)
    background_tasks.add_task(run_pipeline, rec.job_id)

    return rec


@app.get("/jobs", response_model=list[JobRecord])
async def list_jobs_endpoint(limit: int = 50) -> list[JobRecord]:
    return await list_jobs(limit=limit)


@app.get("/jobs/{job_id}", response_model=JobRecord)
async def get_job_endpoint(job_id: str) -> JobRecord:
    rec = await get_job(job_id)
    if rec is None:
        raise HTTPException(404, detail=f"job {job_id} 不存在")
    return rec


@app.get("/jobs/{job_id}/download")
async def download_bundle(job_id: str) -> FileResponse:
    rec = await get_job(job_id)
    if rec is None:
        raise HTTPException(404, detail=f"job {job_id} 不存在")
    if rec.progress.stage != JobStage.DONE:
        raise HTTPException(
            409,
            detail=f"job {job_id} 尚未完成 (当前 stage={rec.progress.stage.value})",
        )

    d = job_dir(job_id)
    # 取 output 下的 .zip (pipeline 会把 bundle zip 放首位)
    zips = list((d / "output").glob("*.zip"))
    if not zips:
        raise HTTPException(500, detail="找不到 bundle zip, 请查看服务端日志")
    zip_path = zips[0]
    return FileResponse(
        path=zip_path,
        media_type="application/zip",
        filename=zip_path.name,
    )


@app.get("/jobs/{job_id}/artifact/{filename}")
async def download_artifact(job_id: str, filename: str) -> FileResponse:
    """下载单个产物 (不打包 zip, 方便直接拿 docx/xlsx/md)."""
    rec = await get_job(job_id)
    if rec is None:
        raise HTTPException(404, detail=f"job {job_id} 不存在")
    d = job_dir(job_id)
    target = (d / "output" / filename).resolve()
    if not target.exists() or not target.is_file():
        raise HTTPException(404, detail=f"产物 {filename} 不存在")
    # 防路径穿越
    if not str(target).startswith(str((d / "output").resolve())):
        raise HTTPException(400, detail="非法路径")
    media = "application/octet-stream"
    if filename.endswith(".docx"):
        media = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif filename.endswith(".xlsx"):
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif filename.endswith(".md"):
        media = "text/markdown; charset=utf-8"
    elif filename.endswith(".zip"):
        media = "application/zip"
    return FileResponse(path=target, media_type=media, filename=filename)


@app.delete("/jobs/{job_id}")
async def delete_job_endpoint(job_id: str) -> dict[str, Any]:
    ok = await delete_job(job_id)
    if not ok:
        raise HTTPException(404, detail=f"job {job_id} 不存在")
    return {"deleted": job_id}


# ================= main =================


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8787,
        reload=True,
    )
