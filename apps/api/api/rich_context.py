"""Store / video evidence collectors for external-game review context.

目标:
  1. 把 `store_url` 真正抓成商店页元数据 + 截图素材
  2. 把 `video_url` 真正抽成关键帧素材
  3. 产出可喂给 LLM 的结构化上下文, 同时补齐 review.json 的 visual/video 字段

设计取向:
  - 本地优先桥接到同级 `ppt-master` 的 `fetch_game_assets.py`, 让网站链路与 Skill 链路共用同一套抓取/抽帧/标注逻辑
  - 如果找不到 `ppt-master` 或桥接失败, 再回退到 game-review 内置 collector, 保持网站可独立运行
  - 证据文件全部落到 `<workdir>/raw_assets/<game_id>/...`, 直接兼容现有 CLI / 视觉索引 Sheet
  - 缺依赖或上游失败时降级为 warning, 不打断整条流水线
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import httpx

try:
    from google_play_scraper import app as gplay_app
    from google_play_scraper import search as gplay_search
except ImportError:  # pragma: no cover - optional dependency
    gplay_app = None
    gplay_search = None

try:
    from imageio_ffmpeg import get_ffmpeg_exe
except ImportError:  # pragma: no cover - optional dependency
    get_ffmpeg_exe = None

try:
    from yt_dlp import YoutubeDL
except ImportError:  # pragma: no cover - optional dependency
    YoutubeDL = None

try:
    from PIL import Image
except ImportError:  # pragma: no cover - Pillow is a project dependency, but keep fallback safe
    Image = None

log = logging.getLogger(__name__)

HTTP_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
HTTP_TIMEOUT = 30.0
MAX_SCREENSHOTS = 8
MAX_DESCRIPTION_CHARS = 3000
MAX_CONTEXT_CHARS = 20000
FRAME_INTERVAL_SECONDS = 12
MAX_VIDEO_FRAMES = 12
PHASH_THRESHOLD = 8
CORE_DIMS_STORE = ["D1", "D7"]
CORE_DIMS_VIDEO = ["D2", "D7"]
_SCENE_ID_RE = re.compile(r"scene_(\d+)", re.I)
APPSTORE_GENERIC_TOKENS = {
    "a", "an", "and", "app", "apps", "battle", "city", "day", "free", "fun",
    "game", "games", "hero", "idle", "island", "last", "legend", "legends",
    "mobile", "of", "online", "quest", "rpg", "sim", "simulator", "story",
    "survival", "the", "tycoon", "war", "world",
}
PPT_MASTER_FETCH_ENV = "PPT_MASTER_FETCH_SCRIPT"


@dataclass(slots=True)
class StoreEvidence:
    source: str
    page_url: str
    title: str
    developer: str
    description: str
    rating: str
    installs: str
    genre: str
    release_info: str
    icon_path: str | None
    screenshot_paths: list[str] = field(default_factory=list)
    video_url: str | None = None
    raw_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class VideoEvidence:
    source_url: str
    resolved_url: str
    title: str
    uploader: str
    duration_seconds: int
    description: str
    frame_paths: list[str] = field(default_factory=list)
    frame_interval_seconds: int = FRAME_INTERVAL_SECONDS
    raw_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RichContextBundle:
    notes: str | None
    enriched_notes: str | None
    store: StoreEvidence | None
    video: VideoEvidence | None
    warnings: list[str]
    review_fields: dict[str, Any]


def _title_tokens(text: str) -> list[str]:
    return [tok for tok in re.split(r"[^a-z0-9]+", (text or "").lower()) if tok]


def _core_title_tokens(text: str) -> set[str]:
    return {
        tok for tok in _title_tokens(text)
        if len(tok) >= 2 and tok not in APPSTORE_GENERIC_TOKENS
    }


def _title_similarity(a: str, b: str) -> float:
    left = "".join(_title_tokens(a))
    right = "".join(_title_tokens(b))
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def _select_appstore_candidate(game_name: str, results: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, str]:
    target_tokens = set(_title_tokens(game_name))
    target_core = _core_title_tokens(game_name)
    ranked: list[tuple[float, float, int, int, dict[str, Any]]] = []

    for app in results:
        title = str(app.get("trackName") or app.get("trackCensoredName") or "")
        if not title:
            continue
        title_tokens = set(_title_tokens(title))
        title_core = _core_title_tokens(title)
        bundle_core = _core_title_tokens(str(app.get("bundleId") or "").replace(".", " "))
        overlap_all = len(target_tokens & title_tokens)
        overlap_core = len(target_core & (title_core | bundle_core))
        similarity = _title_similarity(game_name, title)
        contains = int(
            bool(title and (title.lower() in game_name.lower() or game_name.lower() in title.lower()))
        )
        score = similarity + (0.45 * overlap_core / max(len(target_core), 1)) + (0.12 * contains)
        if target_core and overlap_core == 0:
            score -= 0.30
        ranked.append((score, similarity, overlap_core, overlap_all, app))

    if not ranked:
        return None, "no ranked candidates"

    ranked.sort(key=lambda item: (item[0], item[1], item[2], item[3]), reverse=True)
    best_score, best_similarity, best_core, best_all, best_app = ranked[0]
    second_score = ranked[1][0] if len(ranked) > 1 else -1.0

    if target_core:
        confident = (
            (best_core == len(target_core) and best_similarity >= 0.58)
            or (best_core >= max(1, (len(target_core) + 1) // 2) and best_similarity >= 0.74)
            or best_similarity >= 0.90
        )
    else:
        confident = best_similarity >= 0.88 or (best_all >= max(1, len(target_tokens) - 1) and best_similarity >= 0.78)

    if not confident:
        return None, f"best candidate too weak (score={best_score:.2f}, similarity={best_similarity:.2f})"
    if second_score >= best_score - 0.04 and best_score < 1.15:
        return None, f"best candidate ambiguous (best={best_score:.2f}, second={second_score:.2f})"
    return best_app, f"matched by title score={best_score:.2f}, similarity={best_similarity:.2f}"


def _find_ppt_master_fetch_script() -> Path | None:
    override = os.environ.get(PPT_MASTER_FETCH_ENV, "").strip()
    if override:
        path = Path(override).expanduser().resolve()
        return path if path.exists() else None

    git_root = Path(__file__).resolve().parents[4]
    candidate = git_root / "ppt-master" / "skills" / "ppt-master" / "scripts" / "game_assets" / "fetch_game_assets.py"
    return candidate if candidate.exists() else None


def _ppt_master_dir_name(game_name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\s]+', "-", game_name).strip("-")
    return cleaned[:80] or "unnamed"


def _extract_steam_app_id(store_url: str) -> str | None:
    m = re.search(r"/app/(\d+)", store_url)
    return m.group(1) if m else None


def _load_descriptions_for_game(raw_project_dir: Path) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    desc_path = raw_project_dir / "gameplay" / "descriptions.json"
    if not desc_path.exists():
        return {}, {}, {}
    try:
        payload = json.loads(desc_path.read_text(encoding="utf-8"))
    except Exception:
        return {}, {}, {}

    by_rel: dict[str, str] = {}
    by_scene: dict[str, str] = {}
    store_descs: dict[str, str] = {}
    if not isinstance(payload, dict):
        return by_rel, by_scene, store_descs

    for rel_path, desc in payload.items():
        text = str(desc or "").strip()
        if not text:
            continue
        rel_key = str(rel_path).replace("\\", "/")
        by_rel[rel_key] = text
        stem = Path(rel_key).stem
        if stem:
            by_scene.setdefault(stem, text)
        if rel_key.startswith("store/"):
            store_descs[rel_key] = text
    return by_rel, by_scene, store_descs


def _merge_into_raw_assets(src_dir: Path, final_dir: Path) -> Path:
    if not src_dir.exists():
        return final_dir
    if src_dir.resolve() == final_dir.resolve():
        return final_dir
    final_dir.parent.mkdir(parents=True, exist_ok=True)
    if final_dir.exists():
        shutil.copytree(src_dir, final_dir, dirs_exist_ok=True)
        shutil.rmtree(src_dir)
    else:
        src_dir.rename(final_dir)
    return final_dir


def _pick_store_source(
    stores_meta: dict[str, Any],
    raw_project_dir: Path,
    store_url: str | None,
) -> str | None:
    host = urllib.parse.urlparse(store_url).netloc.lower() if store_url else ""
    if "play.google.com" in host and (raw_project_dir / "store" / "googleplay").exists():
        return "googleplay"
    if ("apps.apple.com" in host or "itunes.apple.com" in host) and (raw_project_dir / "store" / "appstore").exists():
        return "appstore"
    if "steampowered.com" in host and (raw_project_dir / "store" / "steam").exists():
        return "steam"

    for source in ("googleplay", "appstore", "steam"):
        if source in stores_meta and (raw_project_dir / "store" / source).exists():
            return source
    for source in ("googleplay", "appstore", "steam"):
        if (raw_project_dir / "store" / source).exists():
            return source
    return None


def _build_store_evidence_from_ppt_master(
    *,
    project_dir: Path,
    raw_project_dir: Path,
    store_url: str | None,
    stores_meta: dict[str, Any],
    store_descs: dict[str, str],
) -> StoreEvidence | None:
    source = _pick_store_source(stores_meta, raw_project_dir, store_url)
    if not source:
        return None

    source_dir = raw_project_dir / "store" / source
    screenshot_files: list[Path] = []
    for pattern in ("screenshot_*.jpg", "ipad_*.jpg"):
        screenshot_files.extend(sorted(source_dir.glob(pattern)))
    screenshot_paths = [_relative_posix(project_dir, path) for path in screenshot_files]

    icon_path = None
    icon_file = source_dir / "icon.png"
    if icon_file.exists():
        icon_path = _relative_posix(project_dir, icon_file)

    info = stores_meta.get(source, {}) if isinstance(stores_meta, dict) else {}
    if source == "googleplay":
        title = str(info.get("title") or "")
        developer = str(info.get("developer") or "")
        description = str(info.get("description") or "")
        rating = str(info.get("score") or "")
        installs = str(info.get("installs") or info.get("ratings") or "")
        genre = str(info.get("genre") or "")
        release_info = str(info.get("released") or "")
        page_url = (
            f"https://play.google.com/store/apps/details?id={info.get('appId')}&hl=en&gl=us"
            if info.get("appId")
            else (store_url or "")
        )
        video_ref = str(info.get("video_url") or "") or None
    elif source == "appstore":
        title = str(info.get("trackName") or "")
        developer = str(info.get("sellerName") or "")
        description = str(info.get("description") or "")
        rating = str(info.get("averageUserRating") or "")
        installs = str(info.get("userRatingCount") or "")
        genre = ", ".join(str(item) for item in info.get("genres") or [] if str(item).strip())
        release_info = str(info.get("releaseDate") or "")
        page_url = str(info.get("trackViewUrl") or store_url or "")
        video_ref = None
    else:
        title = str(info.get("name") or "")
        developer = ", ".join(str(item) for item in info.get("developers") or [] if str(item).strip())
        description = str(info.get("description") or "")
        rating = ""
        installs = ""
        genre = ", ".join(str(item) for item in info.get("genres") or [] if str(item).strip())
        release_info = str(info.get("release_date") or "")
        steam_id = str(info.get("steam_appid") or "")
        page_url = (
            f"https://store.steampowered.com/app/{steam_id}/"
            if steam_id
            else (store_url or "")
        )
        movie_urls = info.get("movie_urls") or []
        video_ref = str(movie_urls[0]) if movie_urls else None

    raw_metadata = dict(info) if isinstance(info, dict) else {}
    if store_descs:
        raw_metadata["descriptions"] = store_descs

    return StoreEvidence(
        source=source,
        page_url=page_url,
        title=title,
        developer=developer,
        description=_trim_text(description, MAX_DESCRIPTION_CHARS),
        rating=rating,
        installs=installs,
        genre=genre,
        release_info=release_info,
        icon_path=icon_path,
        screenshot_paths=screenshot_paths,
        video_url=video_ref,
        raw_metadata=raw_metadata,
    )


def _probe_video_metadata(video_url: str | None) -> dict[str, Any]:
    if not video_url or YoutubeDL is None:
        return {}
    try:
        with YoutubeDL({"quiet": True, "no_warnings": True, "socket_timeout": 30}) as ydl:
            info = ydl.extract_info(video_url, download=False)
    except Exception as exc:
        log.warning("yt-dlp metadata probe failed: %s", exc)
        return {}
    return info if isinstance(info, dict) else {}


def _build_video_evidence_from_ppt_master(
    *,
    project_dir: Path,
    raw_project_dir: Path,
    video_url: str | None,
    gameplay_meta: dict[str, Any],
    scene_descs: dict[str, str],
) -> VideoEvidence | None:
    frame_files = sorted((raw_project_dir / "gameplay" / "frames").rglob("*.jpg"))
    if not frame_files:
        return None

    frame_paths = [_relative_posix(project_dir, path) for path in frame_files]
    probed = _probe_video_metadata(video_url)
    videos = gameplay_meta.get("videos") or []
    title = str(probed.get("title") or "")
    if not title and videos:
        title = str(Path(videos[0].get("filename") or "").stem)
    duration_seconds = int(probed.get("duration") or 0)
    description = _trim_text(str(probed.get("description") or ""), MAX_DESCRIPTION_CHARS)
    resolved_url = str(probed.get("webpage_url") or video_url or "")
    uploader = str(probed.get("uploader") or "")
    interval_seconds = 5 if gameplay_meta.get("mode") in {"smart", "scene+dedup"} else 0

    raw_metadata = dict(gameplay_meta) if isinstance(gameplay_meta, dict) else {}
    if scene_descs:
        raw_metadata["scene_descriptions"] = scene_descs

    return VideoEvidence(
        source_url=video_url or resolved_url,
        resolved_url=resolved_url or video_url or "",
        title=title,
        uploader=uploader,
        duration_seconds=duration_seconds,
        description=description,
        frame_paths=frame_paths,
        frame_interval_seconds=interval_seconds,
        raw_metadata=raw_metadata,
    )


def _collect_with_ppt_master_fetcher(
    *,
    game_id: str,
    game_name: str,
    store_url: str | None,
    video_url: str | None,
    project_dir: Path,
) -> tuple[StoreEvidence | None, VideoEvidence | None, list[str]] | None:
    fetch_script = _find_ppt_master_fetch_script()
    if fetch_script is None:
        return None

    raw_root = project_dir / "raw_assets"
    raw_root.mkdir(parents=True, exist_ok=True)

    cmd = [sys.executable, str(fetch_script), game_name, "--out", str(raw_root), "--label"]
    if store_url and not video_url:
        cmd.append("--store-only")
    elif video_url and not store_url:
        cmd.append("--gameplay-only")

    if video_url:
        cmd.extend(["--video", video_url])

    if store_url:
        host = urllib.parse.urlparse(store_url).netloc.lower()
        if "play.google.com" in host:
            app_id = _extract_googleplay_id(store_url)
            if app_id:
                cmd.extend(["--gplay-id", app_id])
        elif "apps.apple.com" in host or "itunes.apple.com" in host:
            app_id = _extract_appstore_id(store_url)
            if app_id:
                cmd.extend(["--appstore-id", app_id])
        elif "steampowered.com" in host:
            app_id = _extract_steam_app_id(store_url)
            if app_id:
                cmd.extend(["--steam-id", app_id])

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
        )
    except Exception as exc:
        log.warning("ppt-master fetch bridge failed before execution: %s", exc)
        return None

    if proc.returncode != 0:
        tail = " | ".join(line.strip() for line in (proc.stderr or proc.stdout).splitlines()[-4:] if line.strip())
        log.warning("ppt-master fetch bridge exited %s: %s", proc.returncode, tail)
        return None

    temp_dir = raw_root / _ppt_master_dir_name(game_name)
    final_dir = _merge_into_raw_assets(temp_dir, raw_root / game_id)
    meta_path = final_dir / "metadata.json"
    meta = {}
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            meta = {}

    desc_by_rel, scene_descs, store_descs = _load_descriptions_for_game(final_dir)
    store = _build_store_evidence_from_ppt_master(
        project_dir=project_dir,
        raw_project_dir=final_dir,
        store_url=store_url,
        stores_meta=meta.get("stores", {}) if isinstance(meta, dict) else {},
        store_descs=store_descs,
    )
    video = _build_video_evidence_from_ppt_master(
        project_dir=project_dir,
        raw_project_dir=final_dir,
        video_url=video_url,
        gameplay_meta=meta.get("gameplay", {}) if isinstance(meta, dict) else {},
        scene_descs=scene_descs,
    )

    warnings: list[str] = []
    if store is not None or video is not None:
        warnings.append("素材采集优先使用 ppt-master 主采集器，已与 Skill 流保持同一套逻辑。")
    elif store_url or video_url:
        warnings.append("ppt-master 主采集器未产出素材，已回退到 game-review 内置采集器。")
        return None

    # Keep description index available for later compose/build helpers.
    if store is not None and desc_by_rel:
        store.raw_metadata.setdefault("descriptions", store_descs)
    if video is not None and scene_descs:
        video.raw_metadata.setdefault("scene_descriptions", scene_descs)
    return store, video, warnings


def fetch_asset_context_bundle(
    *,
    game_id: str,
    game_name: str,
    store_url: str | None,
    video_url: str | None,
    notes: str | None,
    output_dir: Path,
) -> RichContextBundle:
    workdir = output_dir
    raw_project_dir = workdir / "raw_assets" / game_id
    raw_project_dir.mkdir(parents=True, exist_ok=True)

    warnings: list[str] = []
    store_evidence: StoreEvidence | None = None
    video_evidence: VideoEvidence | None = None

    bridge = _collect_with_ppt_master_fetcher(
        game_id=game_id,
        game_name=game_name,
        store_url=store_url,
        video_url=video_url,
        project_dir=workdir,
    )
    if bridge is not None:
        store_evidence, video_evidence, bridge_warnings = bridge
        warnings.extend(bridge_warnings)
    else:
        if store_url:
            try:
                store_evidence = _collect_store_evidence(
                    game_name=game_name,
                    store_url=store_url,
                    project_dir=workdir,
                    raw_project_dir=raw_project_dir,
                )
            except Exception as exc:  # pragma: no cover - network / upstream failures vary
                msg = f"商店页自动抓取失败: {type(exc).__name__}: {exc}"
                warnings.append(msg)
                log.warning(msg)

        candidate_video_url = video_url or (store_evidence.video_url if store_evidence else None)
        if candidate_video_url:
            try:
                video_evidence = _collect_video_evidence(
                    video_url=candidate_video_url,
                    project_dir=workdir,
                    raw_project_dir=raw_project_dir,
                )
            except Exception as exc:  # pragma: no cover - external tools / network vary
                msg = f"视频关键帧抽取失败: {type(exc).__name__}: {exc}"
                warnings.append(msg)
                log.warning(msg)

    candidate_video_url = video_url or (store_evidence.video_url if store_evidence else None)

    enriched_notes = compose_enriched_notes(
        notes=notes,
        store=store_evidence,
        video=video_evidence,
    )
    review_fields = _build_review_fields(
        store=store_evidence,
        video=video_evidence,
        store_url=store_url,
        video_url=candidate_video_url,
    )
    save_context_bundle(
        output_dir=workdir,
        store=store_evidence,
        video=video_evidence,
        review_fields=review_fields,
        warnings=warnings,
        enriched_notes=enriched_notes,
    )

    return RichContextBundle(
        notes=notes,
        enriched_notes=enriched_notes,
        store=store_evidence,
        video=video_evidence,
        warnings=warnings,
        review_fields=review_fields,
    )


def compose_enriched_notes(
    *,
    notes: str | None,
    store: StoreEvidence | None,
    video: VideoEvidence | None,
) -> str | None:
    blocks: list[str] = []
    base = (notes or "").strip()
    if base:
        blocks.append(base)

    if store is not None:
        store_desc_values = list(
            dict.fromkeys(
                text.strip()
                for text in (store.raw_metadata.get("descriptions") or {}).values()
                if str(text).strip()
            )
        )[:4]
        blocks.append(
            "\n".join(
                [
                    "[自动抓取商店页证据]",
                    "- 重点服务维度: D1 题材匹配度, D7 美术/素材表达",
                    f"- 来源: {store.source}",
                    f"- 页面: {store.page_url}",
                    f"- 标题: {store.title or '(未识别)'}",
                    f"- 开发者: {store.developer or '(未识别)'}",
                    f"- 品类: {store.genre or '(未识别)'}",
                    f"- 评分: {store.rating or '(未识别)'}",
                    f"- 安装/评分量: {store.installs or '(未识别)'}",
                    f"- 上线信息: {store.release_info or '(未识别)'}",
                    f"- 已抓取截图: {len(store.screenshot_paths)} 张",
                    *([f"- 画面描述样例: {'；'.join(store_desc_values)}"] if store_desc_values else []),
                    "- 商店描述摘要:",
                    _trim_text(store.description, MAX_DESCRIPTION_CHARS) or "(无)",
                ]
            ).strip()
        )

    if video is not None:
        frame_labels = ", ".join(_frame_labels(video.frame_paths)) or "(无)"
        scene_descs = list(
            dict.fromkeys(
                text.strip()
                for text in (video.raw_metadata.get("scene_descriptions") or {}).values()
                if str(text).strip()
            )
        )[:6]
        blocks.append(
            "\n".join(
                [
                    "[自动抽取视频证据]",
                    "- 重点服务维度: D2 核心循环, D7 美术/素材表达",
                    f"- 来源: {video.resolved_url}",
                    f"- 标题: {video.title or '(未识别)'}",
                    f"- 上传者: {video.uploader or '(未识别)'}",
                    f"- 时长: {_format_duration(video.duration_seconds)}",
                    f"- 已抽取关键帧: {len(video.frame_paths)} 张",
                    f"- 关键帧编号: {frame_labels}",
                    *([f"- 关键帧描述样例: {'；'.join(scene_descs)}"] if scene_descs else []),
                    "- 视频描述摘要:",
                    _trim_text(video.description, MAX_DESCRIPTION_CHARS) or "(无)",
                ]
            ).strip()
        )

    combined = "\n\n".join(part for part in blocks if part)
    if not combined:
        return None
    if len(combined) <= MAX_CONTEXT_CHARS:
        return combined
    return combined[:MAX_CONTEXT_CHARS].rstrip() + "\n\n[自动抓取上下文已截断]"


def save_context_bundle(
    *,
    output_dir: Path,
    store: StoreEvidence | None,
    video: VideoEvidence | None,
    review_fields: dict[str, Any],
    warnings: list[str],
    enriched_notes: str | None,
) -> None:
    context_dir = output_dir / "context"
    context_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "store": asdict(store) if store is not None else None,
        "video": asdict(video) if video is not None else None,
        "warnings": warnings,
        "review_fields": review_fields,
        "enriched_notes": enriched_notes,
    }
    (context_dir / "asset_context.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if enriched_notes:
        (context_dir / "asset_context.txt").write_text(enriched_notes, encoding="utf-8")


def _collect_store_evidence(
    *,
    game_name: str,
    store_url: str,
    project_dir: Path,
    raw_project_dir: Path,
) -> StoreEvidence:
    host = urllib.parse.urlparse(store_url).netloc.lower()
    if "play.google.com" in host:
        return _collect_googleplay(game_name=game_name, store_url=store_url, project_dir=project_dir, raw_project_dir=raw_project_dir)
    if "apps.apple.com" in host or "itunes.apple.com" in host:
        return _collect_appstore(game_name=game_name, store_url=store_url, project_dir=project_dir, raw_project_dir=raw_project_dir)
    raise ValueError(f"暂不支持的商店域名: {host or store_url}")


def _collect_appstore(
    *,
    game_name: str,
    store_url: str,
    project_dir: Path,
    raw_project_dir: Path,
) -> StoreEvidence:
    app_id = _extract_appstore_id(store_url)
    if app_id:
        url = f"https://itunes.apple.com/lookup?id={app_id}&country=us&entity=software"
    else:
        term = urllib.parse.quote(game_name)
        url = f"https://itunes.apple.com/search?term={term}&entity=software&country=us&limit=10"

    data = _json_get(url)
    results = data.get("results") if isinstance(data, dict) else None
    if not results:
        raise ValueError("App Store 未返回结果")

    if app_id:
        app = results[0]
    else:
        app, match_reason = _select_appstore_candidate(game_name, results)
        if app is None:
            preview = ", ".join(
                str(item.get("trackName") or "").strip()
                for item in results[:3]
                if str(item.get("trackName") or "").strip()
            ) or "(none)"
            raise ValueError(
                f"App Store 搜索结果过于模糊: {match_reason}; top candidates: {preview}"
            )
        log.info("App Store candidate accepted for %s: %s", game_name, match_reason)

    out_dir = raw_project_dir / "store" / "appstore"
    out_dir.mkdir(parents=True, exist_ok=True)

    icon_path = None
    icon_url = str(app.get("artworkUrl512") or "")
    if icon_url:
        maybe = out_dir / "icon.png"
        if _download(icon_url, maybe):
            icon_path = _relative_posix(project_dir, maybe)

    screenshot_paths: list[str] = []
    screenshots = list(app.get("screenshotUrls") or [])[:MAX_SCREENSHOTS]
    for idx, image_url in enumerate(screenshots, start=1):
        dest = out_dir / f"screenshot_{idx:02d}.jpg"
        if _download(str(image_url), dest):
            screenshot_paths.append(_relative_posix(project_dir, dest))

    metadata = {
        "source": "appstore",
        "trackName": app.get("trackName", ""),
        "bundleId": app.get("bundleId", ""),
        "trackId": app.get("trackId", ""),
        "sellerName": app.get("sellerName", ""),
        "formattedPrice": app.get("formattedPrice", ""),
        "averageUserRating": app.get("averageUserRating", 0),
        "userRatingCount": app.get("userRatingCount", 0),
        "genres": app.get("genres", []),
        "description": app.get("description", ""),
        "version": app.get("version", ""),
        "releaseDate": app.get("releaseDate", ""),
        "trackViewUrl": app.get("trackViewUrl", store_url),
        "icon_path": icon_path,
        "screenshot_paths": screenshot_paths,
    }
    (out_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    rating = str(app.get("averageUserRating") or "")
    ratings = app.get("userRatingCount")
    installs = f"{ratings} ratings" if ratings else ""
    genre = ", ".join(str(item) for item in app.get("genres") or [] if str(item).strip())

    return StoreEvidence(
        source="appstore",
        page_url=str(app.get("trackViewUrl") or store_url),
        title=str(app.get("trackName") or game_name),
        developer=str(app.get("sellerName") or ""),
        description=_trim_text(str(app.get("description") or ""), MAX_DESCRIPTION_CHARS),
        rating=rating,
        installs=installs,
        genre=genre,
        release_info=str(app.get("releaseDate") or ""),
        icon_path=icon_path,
        screenshot_paths=screenshot_paths,
        video_url=None,
        raw_metadata=metadata,
    )


def _collect_googleplay(
    *,
    game_name: str,
    store_url: str,
    project_dir: Path,
    raw_project_dir: Path,
) -> StoreEvidence:
    if gplay_app is None or gplay_search is None:
        raise RuntimeError("google-play-scraper 未安装")

    app_id = _extract_googleplay_id(store_url)
    result: dict[str, Any] | None = None
    if app_id:
        result = _safe_gplay_call(gplay_app, app_id)
    if result is None:
        results = _safe_gplay_call(gplay_search, game_name)
        if results:
            result = _safe_gplay_call(gplay_app, results[0]["appId"])
    if result is None:
        fallback_id = _extract_googleplay_search_app_id(store_url, game_name)
        if fallback_id:
            result = _safe_gplay_call(gplay_app, fallback_id)
    if not result:
        raise ValueError("Google Play 未返回结果")

    out_dir = raw_project_dir / "store" / "googleplay"
    out_dir.mkdir(parents=True, exist_ok=True)

    icon_path = None
    icon_url = str(result.get("icon") or "")
    if icon_url:
        maybe = out_dir / "icon.png"
        if _download(icon_url, maybe):
            icon_path = _relative_posix(project_dir, maybe)

    screenshot_paths: list[str] = []
    screenshots = list(result.get("screenshots") or [])[:MAX_SCREENSHOTS]
    for idx, image_url in enumerate(screenshots, start=1):
        dest = out_dir / f"screenshot_{idx:02d}.jpg"
        if _download(str(image_url), dest):
            screenshot_paths.append(_relative_posix(project_dir, dest))

    page_url = (
        f"https://play.google.com/store/apps/details?id={result.get('appId')}&hl=en&gl=us"
        if result.get("appId")
        else store_url
    )
    metadata = {
        "source": "googleplay",
        "title": result.get("title", ""),
        "appId": result.get("appId", ""),
        "developer": result.get("developer", ""),
        "score": result.get("score", 0),
        "ratings": result.get("ratings", 0),
        "installs": result.get("installs", ""),
        "genre": result.get("genre", ""),
        "description": result.get("description", ""),
        "released": result.get("released", ""),
        "video_url": result.get("video", ""),
        "page_url": page_url,
        "icon_path": icon_path,
        "screenshot_paths": screenshot_paths,
    }
    (out_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return StoreEvidence(
        source="googleplay",
        page_url=page_url,
        title=str(result.get("title") or game_name),
        developer=str(result.get("developer") or ""),
        description=_trim_text(str(result.get("description") or ""), MAX_DESCRIPTION_CHARS),
        rating=str(result.get("score") or ""),
        installs=str(result.get("installs") or result.get("ratings") or ""),
        genre=str(result.get("genre") or ""),
        release_info=str(result.get("released") or ""),
        icon_path=icon_path,
        screenshot_paths=screenshot_paths,
        video_url=str(result.get("video") or "") or None,
        raw_metadata=metadata,
    )


def _collect_video_evidence(
    *,
    video_url: str,
    project_dir: Path,
    raw_project_dir: Path,
) -> VideoEvidence:
    if YoutubeDL is None:
        raise RuntimeError("yt-dlp 未安装")

    videos_dir = raw_project_dir / "gameplay" / "videos"
    frames_dir = raw_project_dir / "gameplay" / "frames"
    videos_dir.mkdir(parents=True, exist_ok=True)
    frames_dir.mkdir(parents=True, exist_ok=True)

    try:
        with YoutubeDL({"quiet": True, "no_warnings": True, "socket_timeout": 30}) as ydl:
            info = ydl.extract_info(video_url, download=False)
    except Exception as exc:
        log.warning("yt-dlp metadata failed, fallback to static thumbnails: %s", exc)
        return _collect_video_static_thumbnail_fallback(
            video_url=video_url,
            info={"title": "", "uploader": "", "duration": 0, "description": ""},
            project_dir=project_dir,
            raw_project_dir=raw_project_dir,
        )

    ffmpeg_exe = _find_ffmpeg()
    if ffmpeg_exe is None:
        return _collect_video_thumbnail_fallback(
            video_url=video_url,
            info=info,
            project_dir=project_dir,
            raw_project_dir=raw_project_dir,
        )

    download_cmd = [
        sys.executable,
        "-m",
        "yt_dlp",
        video_url,
        "-f",
        "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
        "--merge-output-format",
        "mp4",
        "-o",
        str(videos_dir / "%(title).80s__%(id)s.%(ext)s"),
        "--no-playlist",
        "--socket-timeout",
        "30",
        "--retries",
        "3",
        "--no-warnings",
    ]
    try:
        download_proc = subprocess.run(
            download_cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
        )
    except subprocess.TimeoutExpired:
        return _collect_video_thumbnail_fallback(
            video_url=video_url,
            info=info,
            project_dir=project_dir,
            raw_project_dir=raw_project_dir,
        )
    if download_proc.returncode != 0:
        log.warning("yt-dlp download failed, fallback to thumbnails: %s", download_proc.stderr.strip())
        return _collect_video_thumbnail_fallback(
            video_url=video_url,
            info=info,
            project_dir=project_dir,
            raw_project_dir=raw_project_dir,
        )

    video_path = _locate_downloaded_video(videos_dir, info)
    if video_path is None or not video_path.exists():
        return _collect_video_thumbnail_fallback(
            video_url=video_url,
            info=info,
            project_dir=project_dir,
            raw_project_dir=raw_project_dir,
        )

    slug = _safe_slug(video_path.stem)
    frame_dir = frames_dir / slug
    frame_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        ffmpeg_exe,
        "-i",
        str(video_path),
        "-vf",
        f"fps=1/{FRAME_INTERVAL_SECONDS},scale=1280:-2",
        "-q:v",
        "2",
        str(frame_dir / "scene_%04d.jpg"),
        "-y",
        "-loglevel",
        "error",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "ffmpeg 抽帧失败")

    _deduplicate_frames(frame_dir)
    _prune_frames(frame_dir, keep=MAX_VIDEO_FRAMES)
    frame_files = sorted(frame_dir.glob("scene_*.jpg"))
    frame_paths = [_relative_posix(project_dir, frame) for frame in frame_files]

    metadata = {
        "source_url": video_url,
        "resolved_url": str(info.get("webpage_url") or video_url),
        "id": info.get("id", ""),
        "title": info.get("title", ""),
        "uploader": info.get("uploader", ""),
        "duration": int(info.get("duration") or 0),
        "description": _trim_text(str(info.get("description") or ""), MAX_DESCRIPTION_CHARS),
        "frame_interval_seconds": FRAME_INTERVAL_SECONDS,
        "frame_paths": frame_paths,
    }
    gameplay_dir = raw_project_dir / "gameplay"
    gameplay_dir.mkdir(parents=True, exist_ok=True)
    (gameplay_dir / "video_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    try:
        video_path.unlink()
    except OSError:
        log.warning("failed to delete downloaded video: %s", video_path)
    if videos_dir.exists() and not any(videos_dir.iterdir()):
        try:
            videos_dir.rmdir()
        except OSError:
            pass

    return VideoEvidence(
        source_url=video_url,
        resolved_url=metadata["resolved_url"],
        title=str(info.get("title") or ""),
        uploader=str(info.get("uploader") or ""),
        duration_seconds=int(info.get("duration") or 0),
        description=metadata["description"],
        frame_paths=frame_paths,
        frame_interval_seconds=FRAME_INTERVAL_SECONDS,
        raw_metadata=metadata,
    )


def _collect_video_thumbnail_fallback(
    *,
    video_url: str,
    info: dict[str, Any],
    project_dir: Path,
    raw_project_dir: Path,
) -> VideoEvidence:
    frame_dir = raw_project_dir / "gameplay" / "frames" / _safe_slug(str(info.get("id") or info.get("title") or "video"))
    frame_dir.mkdir(parents=True, exist_ok=True)
    frame_paths: list[str] = []
    seen_urls: set[str] = set()
    thumb_index = 0
    for thumb in info.get("thumbnails") or []:
        image_url = str((thumb or {}).get("url") or "").strip()
        if not image_url or image_url in seen_urls:
            continue
        seen_urls.add(image_url)
        thumb_index += 1
        dest = frame_dir / f"scene_{thumb_index:04d}.jpg"
        if _download(image_url, dest):
            frame_paths.append(_relative_posix(project_dir, dest))
        if len(frame_paths) >= min(MAX_VIDEO_FRAMES, 6):
            break

    if not frame_paths:
        return _collect_video_static_thumbnail_fallback(
            video_url=video_url,
            info=info,
            project_dir=project_dir,
            raw_project_dir=raw_project_dir,
        )

    metadata = {
        "source_url": video_url,
        "resolved_url": str(info.get("webpage_url") or video_url),
        "id": info.get("id", ""),
        "title": info.get("title", ""),
        "uploader": info.get("uploader", ""),
        "duration": int(info.get("duration") or 0),
        "description": _trim_text(str(info.get("description") or ""), MAX_DESCRIPTION_CHARS),
        "frame_interval_seconds": 0,
        "frame_paths": frame_paths,
        "fallback": "thumbnails",
    }
    gameplay_dir = raw_project_dir / "gameplay"
    gameplay_dir.mkdir(parents=True, exist_ok=True)
    (gameplay_dir / "video_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return VideoEvidence(
        source_url=video_url,
        resolved_url=metadata["resolved_url"],
        title=str(info.get("title") or ""),
        uploader=str(info.get("uploader") or ""),
        duration_seconds=int(info.get("duration") or 0),
        description=metadata["description"],
        frame_paths=frame_paths,
        frame_interval_seconds=0,
        raw_metadata=metadata,
    )


def _collect_video_static_thumbnail_fallback(
    *,
    video_url: str,
    info: dict[str, Any],
    project_dir: Path,
    raw_project_dir: Path,
) -> VideoEvidence:
    video_id = _extract_youtube_video_id(video_url)
    if not video_id:
        raise RuntimeError("视频下载失败，且无法从 URL 推断 YouTube 视频 id")

    oembed = _youtube_oembed(video_url)
    frame_dir = raw_project_dir / "gameplay" / "frames" / _safe_slug(video_id)
    frame_dir.mkdir(parents=True, exist_ok=True)
    frame_paths: list[str] = []
    candidate_urls = [
        f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg",
        f"https://i.ytimg.com/vi/{video_id}/sddefault.jpg",
        f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
        f"https://i.ytimg.com/vi/{video_id}/0.jpg",
        f"https://i.ytimg.com/vi/{video_id}/1.jpg",
        f"https://i.ytimg.com/vi/{video_id}/2.jpg",
        f"https://i.ytimg.com/vi/{video_id}/3.jpg",
    ]
    seen_hashes: set[bytes] = set()
    idx = 0
    for image_url in candidate_urls:
        idx += 1
        dest = frame_dir / f"scene_{idx:04d}.jpg"
        if not _download(image_url, dest):
            continue
        blob = dest.read_bytes()
        if blob in seen_hashes:
            dest.unlink(missing_ok=True)
            continue
        seen_hashes.add(blob)
        frame_paths.append(_relative_posix(project_dir, dest))
    _deduplicate_frames(frame_dir)
    frame_paths = [_relative_posix(project_dir, p) for p in sorted(frame_dir.glob("scene_*.jpg"))]
    if not frame_paths:
        raise RuntimeError("视频下载失败，且静态 YouTube 缩略图也不可用")

    metadata = {
        "source_url": video_url,
        "resolved_url": video_url,
        "id": video_id,
        "title": str(oembed.get("title") or info.get("title") or video_id),
        "uploader": str(oembed.get("author_name") or info.get("uploader") or ""),
        "duration": int(info.get("duration") or 0),
        "description": _trim_text(str(info.get("description") or ""), MAX_DESCRIPTION_CHARS),
        "frame_interval_seconds": 0,
        "frame_paths": frame_paths,
        "fallback": "youtube-static-thumbnails",
    }
    gameplay_dir = raw_project_dir / "gameplay"
    gameplay_dir.mkdir(parents=True, exist_ok=True)
    (gameplay_dir / "video_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return VideoEvidence(
        source_url=video_url,
        resolved_url=video_url,
        title=metadata["title"],
        uploader=metadata["uploader"],
        duration_seconds=metadata["duration"],
        description=metadata["description"],
        frame_paths=frame_paths,
        frame_interval_seconds=0,
        raw_metadata=metadata,
    )


def _build_review_fields(
    *,
    store: StoreEvidence | None,
    video: VideoEvidence | None,
    store_url: str | None,
    video_url: str | None,
) -> dict[str, Any]:
    sources: list[dict[str, str]] = []
    if video_url:
        sources.append({"type": "video", "url": video_url})
    if store_url:
        sources.append({"type": "store", "url": store_url})

    visual_catalog = {"store": _build_visual_catalog(store)}
    video_evidence = {
        "sources": sources,
        "frame_analysis": {
            "key_scenes_human_read": _build_video_scenes(video),
        },
    }
    return {
        "visual_catalog": visual_catalog,
        "video_evidence": video_evidence,
    }


def _build_visual_catalog(store: StoreEvidence | None) -> list[dict[str, Any]]:
    if store is None:
        return []
    items: list[dict[str, Any]] = []
    desc_map = store.raw_metadata.get("descriptions") or {}
    for idx, rel_path in enumerate(store.screenshot_paths, start=1):
        rel_key = rel_path.replace("\\", "/")
        desc = str(desc_map.get(rel_key) or "").strip()
        if not desc:
            rel_suffix = "/".join(rel_key.split("/")[-4:])
            for key, value in desc_map.items():
                norm_key = str(key).replace("\\", "/")
                if norm_key == rel_suffix or rel_key.endswith(norm_key):
                    desc = str(value or "").strip()
                    if desc:
                        break
        items.append(
            {
                "code": f"商店图 {idx}",
                "path": rel_path,
                "category": f"{store.source} 商店截图",
                "label": f"{store.source} 商店第 {idx} 张",
                "desc": desc or "自动抓取自商店页，优先用于核对 D1 题材卖点与 D7 素材表达。",
            }
        )
    return items


def _build_video_scenes(video: VideoEvidence | None) -> list[dict[str, Any]]:
    if video is None:
        return []
    scenes: list[dict[str, Any]] = []
    desc_map = video.raw_metadata.get("scene_descriptions") or {}
    for rel_path in video.frame_paths:
        scene_name = Path(rel_path).stem
        secs = _scene_seconds(scene_name, video.frame_interval_seconds)
        desc = str(desc_map.get(scene_name) or "").strip()
        scenes.append(
            {
                "frame": f"{scene_name} ({_format_duration(secs)})",
                "content": desc or "自动抽取关键帧，建议复核开场体验、核心循环表达和画面素材一致性。",
                "dims_affected": CORE_DIMS_VIDEO,
            }
        )
    return scenes


def _extract_googleplay_id(store_url: str) -> str | None:
    parsed = urllib.parse.urlparse(store_url)
    query = urllib.parse.parse_qs(parsed.query)
    value = query.get("id", [None])[0]
    return value.strip() if isinstance(value, str) and value.strip() else None


def _extract_googleplay_search_app_id(store_url: str, game_name: str) -> str | None:
    parsed = urllib.parse.urlparse(store_url)
    target_url = store_url
    if "play.google.com" not in parsed.netloc.lower():
        target_url = (
            "https://play.google.com/store/search?"
            f"q={urllib.parse.quote(game_name)}&c=apps&hl=en&gl=us"
        )

    headers = {"User-Agent": HTTP_USER_AGENT}
    with httpx.Client(timeout=HTTP_TIMEOUT, follow_redirects=True, headers=headers) as client:
        resp = client.get(target_url)
        resp.raise_for_status()
        html = resp.text
    m = re.search(r"/store/apps/details\?id=([^\"&]+)", html)
    if not m:
        return None
    return m.group(1)


def _extract_youtube_video_id(video_url: str) -> str | None:
    parsed = urllib.parse.urlparse(video_url)
    host = parsed.netloc.lower()
    if "youtu.be" in host:
        value = parsed.path.strip("/").split("/")[0]
        return value or None
    if "youtube.com" in host:
        query = urllib.parse.parse_qs(parsed.query)
        value = query.get("v", [None])[0]
        if isinstance(value, str) and value.strip():
            return value.strip()
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 2 and parts[0] in {"embed", "shorts"}:
            return parts[1]
    return None


def _youtube_oembed(video_url: str) -> dict[str, Any]:
    target = "https://www.youtube.com/oembed?" + urllib.parse.urlencode(
        {"url": video_url, "format": "json"}
    )
    try:
        data = _json_get(target)
    except Exception:
        return {}
    return data


def _extract_appstore_id(store_url: str) -> str | None:
    m = re.search(r"/id(\d+)", store_url)
    return m.group(1) if m else None


def _json_get(url: str) -> dict[str, Any]:
    headers = {"User-Agent": HTTP_USER_AGENT}
    with httpx.Client(timeout=HTTP_TIMEOUT, follow_redirects=True, headers=headers) as client:
        resp = client.get(url)
        resp.raise_for_status()
        data = resp.json()
    if not isinstance(data, dict):
        raise ValueError(f"unexpected json payload from {url}")
    return data


def _download(url: str, dest: Path) -> bool:
    headers = {"User-Agent": HTTP_USER_AGENT}
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT, follow_redirects=True, headers=headers) as client:
            resp = client.get(url)
            resp.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(resp.content)
        return True
    except Exception as exc:  # pragma: no cover - download failures are best effort
        log.warning("asset download skipped: %s -> %s (%s)", url, dest, exc)
        return False


def _safe_gplay_call(func, *args):
    try:
        return func(*args)
    except TypeError:
        return func(*args, lang="en", country="us")
    except Exception as exc:
        log.warning("google-play-scraper call failed: %s", exc)
        return None


def _find_ffmpeg() -> str | None:
    if get_ffmpeg_exe is not None:
        try:
            return get_ffmpeg_exe()
        except Exception:
            pass
    return shutil.which("ffmpeg")


def _locate_downloaded_video(videos_dir: Path, info: dict[str, Any]) -> Path | None:
    vid = str(info.get("id") or "").strip()
    candidates = sorted(videos_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    if vid:
        for path in candidates:
            if f"__{vid}" in path.stem:
                return path
    return candidates[0] if candidates else None


def _phash(img_path: Path, hash_size: int = 8) -> int | None:
    if Image is None:
        return None
    try:
        img = Image.open(img_path).convert("L").resize((hash_size + 1, hash_size), Image.LANCZOS)
        pixels = list(img.getdata())
        avg = sum(pixels) / len(pixels)
        return sum(1 << idx for idx, value in enumerate(pixels) if value > avg)
    except Exception:
        return None


def _hamming(h1: int, h2: int) -> int:
    return bin(h1 ^ h2).count("1")


def _deduplicate_frames(frame_dir: Path, threshold: int = PHASH_THRESHOLD) -> int:
    frames = sorted(frame_dir.glob("scene_*.jpg"))
    hashes: list[int] = []
    removed = 0
    for frame in frames:
        current = _phash(frame)
        if current is None:
            continue
        if any(_hamming(current, previous) < threshold for previous in hashes):
            frame.unlink(missing_ok=True)
            removed += 1
        else:
            hashes.append(current)
    return removed


def _prune_frames(frame_dir: Path, *, keep: int) -> None:
    frames = sorted(frame_dir.glob("scene_*.jpg"))
    if len(frames) <= keep:
        return
    keep_indices = {
        round(idx * (len(frames) - 1) / (keep - 1))
        for idx in range(keep)
    }
    for idx, frame in enumerate(frames):
        if idx not in keep_indices:
            frame.unlink(missing_ok=True)


def _frame_labels(frame_paths: list[str]) -> list[str]:
    return [Path(path).stem for path in frame_paths]


def _scene_seconds(scene_name: str, interval_seconds: int) -> int:
    m = _SCENE_ID_RE.search(scene_name)
    if not m:
        return 0
    if interval_seconds <= 0:
        return 0
    return max(0, (int(m.group(1)) - 1) * interval_seconds)


def _format_duration(seconds: int) -> str:
    seconds = max(0, int(seconds))
    minutes, rem = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{rem:02d}"
    return f"{minutes:02d}:{rem:02d}"


def _trim_text(value: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", value or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + " ..."


def _safe_slug(value: str) -> str:
    safe = re.sub(r"[^\w\u4e00-\u9fa5\-]+", "_", value, flags=re.U).strip("_")
    return safe[:80] or "video"


def _relative_posix(project_dir: Path, target: Path) -> str:
    return target.resolve().relative_to(project_dir.resolve()).as_posix()
