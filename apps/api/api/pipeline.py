"""Pipeline · 把 game-review CLI 编排成 async 流水线

4 个 stage:
  1. FETCH     把用户上传的 raw_assets / review.json 解压到 workdir (Phase 3 不自动抓取)
  2. SCORE     调 ai_stub (内部优先 Compass, 失败回退 stub) 产出 review.json (如果用户没提供)
  3. GENERATE  调 game-review CLI 生成 docx/xlsx/md 三件套
  4. PACKAGE   zip 产物, 写好下载链接

Phase 3 的 fetch 和 score 都是上传友好的: 用户可以自己上传 raw_assets.zip 和 review.json,
没上传的时候由 ai_stub 负责生成 review.json (内部优先 Compass, 失败回退 stub).
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

from . import ai_stub, article_fetch, rich_context
from .job_store import append_activity, get_job, job_dir, update_progress
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
            message="stage 1/4: 准备素材与评审上下文",
            details=[
                "检查用户上传的 raw_assets.zip / review.json",
                "识别参考文章链接",
                "如命中 mp.weixin 或参考文章 URL，则自动抓正文并并入评审上下文",
                "如提供 Google Play / App Store 链接，则自动抓商店文案与截图",
                "如提供 YouTube 链接，则自动抽关键帧并写入 raw_assets",
            ],
        )

        # workdir 内结构: <workdir>/raw_assets/<game_id>/...
        # 如果用户上传了 raw_assets.zip, 解压进去; 否则空
        raw_zip = input_dir / "raw_assets.zip"
        user_review = input_dir / "review.json"
        if raw_zip.exists():
            ra_root = workdir / "raw_assets"
            _unzip_into(raw_zip, ra_root)
            log.info("fetch: 解压 raw_assets.zip → %s", ra_root)
            await append_activity(
                job_id,
                stage=JobStage.FETCHING,
                message="已解压 raw_assets.zip，视觉素材可供 CLI 使用",
            )
        else:
            await append_activity(
                job_id,
                stage=JobStage.FETCHING,
                message="未上传 raw_assets.zip，跳过素材解压",
            )

        enriched_notes = req.notes
        asset_bundle = None
        if user_review.exists():
            await append_activity(
                job_id,
                stage=JobStage.FETCHING,
                message="已上传 review.json，本次跳过参考文章抓取，但仍会补抓商店页/视频素材供报告使用",
            )
        else:
            candidate_urls = article_fetch.resolve_auto_fetch_urls(
                reference_url=req.reference_url,
                notes=req.notes,
            )
            if candidate_urls:
                await update_progress(
                    job_id,
                    percent=22,
                    message="stage 1/4: 抓取参考文章正文",
                    details=[
                        f"已识别 {len(candidate_urls)} 个待抓取链接",
                        *candidate_urls,
                    ],
                )
                bundle = await asyncio.to_thread(
                    article_fetch.fetch_context_bundle,
                    reference_url=req.reference_url,
                    notes=req.notes,
                    output_dir=workdir,
                )
                enriched_notes = bundle.enriched_notes
                if bundle.articles:
                    await append_activity(
                        job_id,
                        stage=JobStage.FETCHING,
                        message=(
                            f"已抓取 {len(bundle.articles)} 篇参考文章正文"
                            f"（{', '.join(article.title for article in bundle.articles)}）"
                        ),
                    )
                if bundle.skipped_urls:
                    await append_activity(
                        job_id,
                        stage=JobStage.FETCHING,
                        message=f"有 {len(bundle.skipped_urls)} 个链接抓取失败，已忽略并继续评审",
                    )
            else:
                await append_activity(
                    job_id,
                    stage=JobStage.FETCHING,
                    message="未发现可自动抓取的参考文章链接，继续使用手填备注",
                )

        asset_bundle = await asyncio.to_thread(
            rich_context.fetch_asset_context_bundle,
            game_id=game_id,
            game_name=req.game_name,
            store_url=req.store_url,
            video_url=req.video_url,
            notes=enriched_notes,
            output_dir=workdir,
        )
        enriched_notes = asset_bundle.enriched_notes
        if asset_bundle.store is not None:
            await append_activity(
                job_id,
                stage=JobStage.FETCHING,
                message=(
                    f"已抓取 {asset_bundle.store.source} 商店页证据，"
                    f"落盘 {len(asset_bundle.store.screenshot_paths)} 张截图"
                ),
            )
        if asset_bundle.video is not None:
            await append_activity(
                job_id,
                stage=JobStage.FETCHING,
                message=(
                    f"已抽取 {len(asset_bundle.video.frame_paths)} 张视频关键帧，"
                    "并写入 raw_assets 供视觉索引与评审上下文复用"
                ),
            )
        for warning in asset_bundle.warnings:
            await append_activity(
                job_id,
                stage=JobStage.FETCHING,
                message=warning,
            )

        # ===== stage 2: score =====
        await update_progress(
            job_id,
            stage=JobStage.SCORING,
            percent=35,
            message="stage 2/4: 生成 review.json (用户提供 or Compass/stub)",
            details=[
                "若已上传 review.json，则直接复用",
                "否则使用 Compass 基于表单、备注和自动抓取正文生成结构化评审",
            ],
        )

        if user_review.exists():
            # 用户直接上传了 review.json → 直接放到 workdir/review/
            review_dir = workdir / "review"
            review_dir.mkdir(parents=True, exist_ok=True)
            target = review_dir / f"{game_id}_review.json"
            shutil.copy2(user_review, target)
            log.info("score: 用户上传的 review.json → %s", target)
            await append_activity(
                job_id,
                stage=JobStage.SCORING,
                message="已复用用户上传的 review.json，跳过 Compass 生成",
            )
        else:
            await append_activity(
                job_id,
                stage=JobStage.SCORING,
                message="开始调用 Compass 生成结构化 review.json",
            )
            generated = await asyncio.to_thread(
                ai_stub.generate_stub_review,
                project_id=game_id,
                project_name=req.game_name,
                mode=req.mode.value,
                store_url=req.store_url,
                video_url=req.video_url,
                reference_url=req.reference_url,
                notes=enriched_notes,
                extra_fields=asset_bundle.review_fields if asset_bundle is not None else None,
            )
            await asyncio.to_thread(
                ai_stub.write_review_json,
                workdir,
                generated,
                game_id,
            )
            log.info("score: AI provider 写入 review.json")
            await append_activity(
                job_id,
                stage=JobStage.SCORING,
                message="review.json 已生成并写入工作目录",
            )

        await asyncio.sleep(0.3)

        # ===== stage 3: generate =====
        await update_progress(
            job_id,
            stage=JobStage.GENERATING,
            percent=60,
            message="stage 3/4: 调 game-review CLI 生成 docx/xlsx/md 三件套",
            details=[
                "执行 game-review review",
                "产出 Word / Excel / Markdown 报告",
            ],
        )

        cli = _find_cli()
        cmd = [*cli, "review", str(workdir), "--mode", req.mode.value]
        if req.with_visuals:
            cmd.append("--with-visuals")

        await append_activity(
            job_id,
            stage=JobStage.GENERATING,
            message=f"开始执行 CLI：{' '.join(cmd)}",
        )

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

        await append_activity(
            job_id,
            stage=JobStage.GENERATING,
            message=f"CLI 已生成 {len(artifacts)} 个报告产物",
        )

        # ===== stage 4: package =====
        await update_progress(
            job_id,
            stage=JobStage.PACKAGING,
            percent=85,
            message="stage 4/4: 打包下载",
            details=[
                "收集 docx / xlsx / md 产物",
                "打成 bundle.zip 供下载",
            ],
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
            details=[
                f"bundle: {bundle_name}",
                *all_files[1:],
            ],
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
            details=["请展开下方错误详情查看失败原因"],
            error=str(e),
        )
