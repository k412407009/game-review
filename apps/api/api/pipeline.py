"""Pipeline · 把 game-review CLI 编排成 async 流水线

4 个 stage:
  1. FETCH     把用户上传的 raw_assets / review.json 解压到 workdir (Phase 3 不自动抓取)
  2. SCORE     调 ai_stub (或未来真实 LLM) 产出 review.json (如果用户没提供)
  3. GENERATE  调 game-review CLI 生成 docx/xlsx/md 三件套
  4. PACKAGE   zip 产物, 写好下载链接

Phase 3 的 fetch 和 score 都是 stub-friendly: 用户可以自己上传 raw_assets.zip 和 review.json,
没上传的时候走 stub (fetch 为空, score 用 ai_stub).
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from . import ai_stub
from .job_store import get_job, job_dir, update_progress
from .schemas import JobStage

log = logging.getLogger(__name__)


# ======== helpers ========


def _sanitize_game_id(s: str) -> str:
    import re
    safe = re.sub(r"[^\w\u4e00-\u9fa5\-]", "_", s)
    return safe.strip("_") or "project"


def _unzip_into(zip_path: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest)


def _find_cli() -> list[str]:
    """找到可用的 game-review CLI 入口.

    优先级:
      1. 环境变量 GAME_REVIEW_CLI (例如: "/path/to/venv/bin/game-review")
      2. 当前 Python 的 game_review.cli 模块 (同进程同 Python, 最稳)
      3. PATH 里的 game-review
    """
    import os

    env = os.environ.get("GAME_REVIEW_CLI")
    if env:
        return [env]
    return [sys.executable, "-m", "game_review.cli"]


def _zip_output(output_dir: Path, dest_zip: Path) -> None:
    dest_resolved = dest_zip.resolve()
    with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in output_dir.rglob("*"):
            if not p.is_file():
                continue
            if p.resolve() == dest_resolved:
                continue
            zf.write(p, arcname=p.relative_to(output_dir))


# ======== pipeline ========


async def run_pipeline(job_id: str) -> None:
    """整个 4-stage 流水线. 失败时标记 stage=FAILED 并写 error."""
    rec = await get_job(job_id)
    if rec is None:
        log.error("pipeline: job %s 不存在", job_id)
        return

    req = rec.request
    d = job_dir(job_id)
    input_dir = d / "input"
    workdir = d / "workdir"
    output_dir = d / "output"

    game_id = _sanitize_game_id(req.game_id)

    try:
        # ===== stage 1: fetch =====
        await update_progress(
            job_id,
            stage=JobStage.FETCHING,
            percent=10,
            message="stage 1/4: 准备素材 (解压用户上传 or 跳过)",
        )

        # workdir 内结构: <workdir>/raw_assets/<game_id>/...
        # 如果用户上传了 raw_assets.zip, 解压进去; 否则空
        raw_zip = input_dir / "raw_assets.zip"
        if raw_zip.exists():
            ra_root = workdir / "raw_assets"
            _unzip_into(raw_zip, ra_root)
            log.info("fetch: 解压 raw_assets.zip → %s", ra_root)

        # Phase 3 不实现自动抓取; 记录 URL 备查
        await asyncio.sleep(0.3)

        # ===== stage 2: score =====
        await update_progress(
            job_id,
            stage=JobStage.SCORING,
            percent=35,
            message="stage 2/4: 生成 review.json (用户提供 or AI stub)",
        )

        user_review = input_dir / "review.json"
        if user_review.exists():
            # 用户直接上传了 review.json → 直接放到 workdir/review/
            review_dir = workdir / "review"
            review_dir.mkdir(parents=True, exist_ok=True)
            target = review_dir / f"{game_id}_review.json"
            shutil.copy2(user_review, target)
            log.info("score: 用户上传的 review.json → %s", target)
        else:
            # 调 AI stub
            stub = ai_stub.generate_stub_review(
                project_id=game_id,
                project_name=req.game_name,
                mode=req.mode.value,
                store_url=req.store_url,
                video_url=req.video_url,
                notes=req.notes,
            )
            ai_stub.write_review_json(workdir, stub, game_id=game_id)
            log.info("score: AI stub 写入 review.json")

        await asyncio.sleep(0.3)

        # ===== stage 3: generate =====
        await update_progress(
            job_id,
            stage=JobStage.GENERATING,
            percent=60,
            message="stage 3/4: 调 game-review CLI 生成 docx/xlsx/md 三件套",
        )

        cli = _find_cli()
        cmd = [*cli, "review", str(workdir), "--mode", req.mode.value]
        if req.with_visuals:
            cmd.append("--with-visuals")

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout_b, _ = await proc.communicate()
        stdout = stdout_b.decode("utf-8", errors="replace")
        log.info("generate stdout:\n%s", stdout)

        if proc.returncode != 0:
            raise RuntimeError(
                f"game-review CLI 返回非 0 (code={proc.returncode}):\n{stdout}"
            )

        # 把 workdir/review/*.{docx,xlsx,md} 产物搬到 output/
        review_out = workdir / "review"
        artifacts: list[str] = []
        for ext in (".docx", ".xlsx", ".md"):
            for p in review_out.glob(f"*{ext}"):
                # review.json 是输入不是产物, 跳过
                if p.suffix == ".json":
                    continue
                if p.name.endswith("_review.json"):
                    continue
                target = output_dir / p.name
                shutil.copy2(p, target)
                artifacts.append(p.name)

        if not artifacts:
            raise RuntimeError("generate 成功但没找到产物 (docx/xlsx/md), 请查看 stdout")

        # ===== stage 4: package =====
        await update_progress(
            job_id,
            stage=JobStage.PACKAGING,
            percent=85,
            message="stage 4/4: 打包下载",
        )

        zip_path = output_dir / f"{game_id}_review_bundle.zip"
        _zip_output(output_dir, zip_path)

        # 把 zip 自己也列进 artifacts (首位)
        bundle_name = zip_path.name
        all_files = [bundle_name] + [a for a in artifacts if a != bundle_name]

        download_url = f"/jobs/{job_id}/download"

        await update_progress(
            job_id,
            stage=JobStage.DONE,
            percent=100,
            message=f"完成, {len(artifacts)} 个产物已打包",
            artifacts=all_files,
            download_url=download_url,
        )
        log.info("pipeline done: %s", job_id)

    except Exception as e:
        log.exception("pipeline failed: %s", job_id)
        await update_progress(
            job_id,
            stage=JobStage.FAILED,
            percent=100,
            message=f"失败: {type(e).__name__}",
            error=str(e),
        )
