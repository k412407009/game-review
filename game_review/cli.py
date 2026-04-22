"""game-review CLI · subcommands

Usage:
    game-review review <project_dir> [--mode internal-ppt|external-game] [--with-visuals] [--quiet]
    game-review summary <projects_root>
    game-review visuals <project_dir> [--xlsx <path>] [--quiet]
    game-review version
    game-review --help

每个 subcommand 对应 skill 脚本目录下的一个入口:
    review   → skills/game-review/scripts/review/generate_review.py:main
    summary  → skills/game-review/scripts/review/build_summary.py:main
    visuals  → skills/game-review/scripts/review/add_visual_sheet.py:main

CLI 层只做参数透传, 不改业务逻辑, 避免两边分叉。
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Any

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except Exception:
    pass

from game_review import __version__


def _find_skill_scripts_dir() -> Path:
    """找到 skills/game-review/scripts/review/ 目录.

    两种情况:
      1. editable 安装 (pip install -e .): game_review/__file__ 在 repo 下,
         往上一级就是 repo 根, 拼 skills/game-review/scripts/review 即可
      2. 非 editable: 目前不支持 (Phase 2 定位本地开发; Phase 3 Web 部署时会重构成
         把 skill 脚本打进 package_data)
    """
    pkg_dir = Path(__file__).resolve().parent
    repo_root = pkg_dir.parent
    scripts_dir = repo_root / "skills" / "game-review" / "scripts" / "review"
    if not scripts_dir.exists():
        raise FileNotFoundError(
            f"找不到 skill 脚本目录: {scripts_dir}\n"
            "  当前 CLI 只支持 editable 安装 (pip install -e .), "
            "预计 Phase 3 Web 化时打包进 package_data。"
        )
    return scripts_dir


# 在 import skill 脚本前注入 sys.path
_SKILL_SCRIPTS_DIR = _find_skill_scripts_dir()
if str(_SKILL_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SKILL_SCRIPTS_DIR))


def _lazy_import(mod_name: str) -> Any:
    """按需 import skill 脚本, 避免启动 game-review --help 时也触发重依赖加载。"""
    return importlib.import_module(mod_name)


def _find_review_json(project_dir: Path) -> Path | None:
    review_dir = project_dir / "review"
    if not review_dir.exists():
        return None
    candidates = sorted(review_dir.glob("*_review.json"))
    return candidates[0] if candidates else None


def _count_files(root: Path, suffixes: tuple[str, ...]) -> int:
    if not root.exists():
        return 0
    return sum(1 for path in root.rglob("*") if path.is_file() and path.suffix.lower() in suffixes)


def _cmd_doctor(args: argparse.Namespace) -> int:
    project_dir = Path(args.project_dir).resolve()
    blockers: list[str] = []
    warnings: list[str] = []

    def _line(status: str, label: str, detail: str) -> None:
        print(f"[{status}] {label}: {detail}")

    print("== game-review doctor ==")
    if project_dir.exists():
        _line("OK", "project", str(project_dir))
    else:
        _line("MISS", "project", f"目录不存在：{project_dir}")
        return 2

    review_dir = project_dir / "review"
    if review_dir.exists():
        _line("OK", "review_dir", str(review_dir))
    else:
        _line("MISS", "review_dir", f"未找到 {review_dir}")
        blockers.append("缺少 review/ 目录")

    json_path = _find_review_json(project_dir)
    review_data: dict[str, Any] = {}
    if json_path is None:
        _line("MISS", "review.json", "未找到 review/*_review.json")
        blockers.append("缺少 *_review.json")
    else:
        try:
            review_data = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception as exc:
            _line("MISS", "review.json", f"无法解析：{exc}")
            blockers.append("review.json 无法解析")
        else:
            _line("OK", "review.json", str(json_path))
            required = ("project", "verdict", "scores", "issues")
            missing = [key for key in required if key not in review_data]
            if missing:
                _line("WARN", "schema", f"缺少字段：{', '.join(missing)}")
                warnings.append(f"review.json 缺少字段：{', '.join(missing)}")
            else:
                reviewers = len(review_data.get("reviewers") or [])
                issues = len(review_data.get("issues") or [])
                _line("OK", "schema", f"project={review_data.get('project')} reviewers={reviewers} issues={issues}")

    raw_root = project_dir / "raw_assets"
    if raw_root.exists():
        store_count = _count_files(raw_root / "", (".jpg", ".jpeg", ".png", ".webp"))
        frame_count = _count_files(raw_root / "", (".jpg", ".jpeg", ".png"))
        desc_count = len(list(raw_root.rglob("descriptions.json")))
        labels_count = len(list(raw_root.rglob("labels.json")))
        _line(
            "OK",
            "raw_assets",
            f"store/frame 图片 {store_count} 张；descriptions.json {desc_count} 个；labels.json {labels_count} 个",
        )
    else:
        _line("WARN", "raw_assets", "未找到 raw_assets/；external-game 模式的视觉索引会退化")
        warnings.append("未找到 raw_assets/")

    visual_catalog = ((review_data.get("visual_catalog") or {}).get("store") or []) if review_data else []
    video_scenes = (
        (((review_data.get("video_evidence") or {}).get("frame_analysis") or {}).get("key_scenes_human_read") or [])
        if review_data else []
    )
    if visual_catalog:
        _line("OK", "visual_catalog.store", f"{len(visual_catalog)} 条")
    elif review_data:
        _line("WARN", "visual_catalog.store", "未提供；Excel 商店图区将依赖 raw_assets 自动扫描")
        warnings.append("visual_catalog.store 为空")

    if video_scenes:
        _line("OK", "video_evidence", f"{len(video_scenes)} 条关键场景")
    elif review_data:
        _line("WARN", "video_evidence", "未提供；如果要做 external-game 视觉索引，建议补齐")
        warnings.append("video_evidence 为空")

    review_outputs = sorted(review_dir.glob("*_review.docx")) if review_dir.exists() else []
    excel_outputs = sorted(review_dir.glob("*_review.xlsx")) if review_dir.exists() else []
    md_outputs = sorted(review_dir.glob("*_subjective_responses.md")) if review_dir.exists() else []
    if review_outputs or excel_outputs or md_outputs:
        _line(
            "OK",
            "artifacts",
            f"docx={len(review_outputs)} xlsx={len(excel_outputs)} md={len(md_outputs)}",
        )
    else:
        _line("WARN", "artifacts", "尚未生成评审产物")

    print("\n总结:")
    if blockers:
        print(f"- 阻塞项 {len(blockers)} 个：")
        for item in blockers:
            print(f"  - {item}")
    else:
        print("- 没有阻塞项。")
    if warnings:
        print(f"- 提醒 {len(warnings)} 个：")
        for item in warnings:
            print(f"  - {item}")
    else:
        print("- 当前项目结构完整。")

    print("\n下一步建议:")
    if blockers:
        print("- 先补齐 review.json / review 目录，再运行正式评审。")
    else:
        print(f"- 生成三件套：game-review review {project_dir}")
        print(f"- 如果是外部游戏并要视觉索引：game-review review {project_dir} --mode external-game --with-visuals")
    return 0 if not blockers else 2


# ================= subcommand handlers =================


def _cmd_review(args: argparse.Namespace) -> int:
    """game-review review <project_dir> → generate_review.main"""
    passthrough: list[str] = [str(args.project_dir), "--mode", args.mode]
    if args.with_visuals:
        passthrough.append("--with-visuals")
    if args.quiet:
        passthrough.append("--quiet")
    mod = _lazy_import("generate_review")
    return int(mod.main(passthrough))


def _cmd_summary(args: argparse.Namespace) -> int:
    """game-review summary <projects_root> → build_summary.main"""
    mod = _lazy_import("build_summary")
    return int(mod.main(["game-review-summary", str(args.projects_root)]))


def _cmd_visuals(args: argparse.Namespace) -> int:
    """game-review visuals <project_dir> [--xlsx] → add_visual_sheet.main"""
    passthrough: list[str] = [str(args.project_dir)]
    if args.xlsx:
        passthrough.extend(["--xlsx", str(args.xlsx)])
    if args.quiet:
        passthrough.append("--quiet")
    mod = _lazy_import("add_visual_sheet")
    return int(mod.main(passthrough))


def _cmd_version(_: argparse.Namespace) -> int:
    print(f"game-review {__version__}")
    return 0


# ================= argparse wiring =================


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="game-review",
        description=(
            "5 评委 × 7 维度评审 CLI。对已上线的外部游戏 (商店页 + 视频) "
            "或内部立项 PPT, 用 '资深制作人 + 战略策略 + 玩法系统 + 用户运营 + 投放运营' "
            "5 个视角打分, 产出 Word + Excel + 主观 MD 三件套。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  # 内部 PPT 评审 (默认)\n"
            "  game-review review /path/to/project_dir\n"
            "\n"
            "  # 外部游戏评审, 带视觉索引 sheet\n"
            "  game-review review /path/to/project_dir --mode external-game --with-visuals\n"
            "\n"
            "  # 跨项目汇总\n"
            "  game-review summary /path/to/projects_root\n"
            "\n"
            "  # 仅给已有 xlsx 追加视觉索引 sheet\n"
            "  game-review visuals /path/to/project_dir --xlsx /path/to/report.xlsx\n"
            "\n"
            "  # 评审前先做项目体检\n"
            "  game-review doctor /path/to/project_dir\n"
        ),
    )
    parser.add_argument("-V", "--version", action="version", version=f"game-review {__version__}")

    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    # review
    p_review = sub.add_parser(
        "review",
        help="读 review.json, 生成 Word/Excel/Markdown 三件套",
        description="读 <project_dir>/review/<project>_review.json, 产出评审三件套 (+ 可选视觉索引 sheet)。",
    )
    p_review.add_argument("project_dir", type=Path, help="项目目录, 需含 review/<project>_review.json")
    p_review.add_argument(
        "--mode",
        choices=["internal-ppt", "external-game"],
        default="internal-ppt",
        help="评审模式, 默认 internal-ppt; external-game 建议配 --with-visuals",
    )
    p_review.add_argument("--with-visuals", action="store_true", help="追加 '视觉索引' Sheet")
    p_review.add_argument("--quiet", action="store_true", help="静默模式")
    p_review.set_defaults(func=_cmd_review)

    # summary
    p_summary = sub.add_parser(
        "summary",
        help="扫描 projects_root, 产出跨项目评审汇总 md",
        description="扫描 <projects_root>/*/review/*_review.json, 产出 <projects_root>/review-summary.md。",
    )
    p_summary.add_argument("projects_root", type=Path, help="项目根目录 (含多个子项目)")
    p_summary.set_defaults(func=_cmd_summary)

    # visuals
    p_visuals = sub.add_parser(
        "visuals",
        help="给已有 xlsx 追加 '视觉索引' Sheet (可独立调用)",
        description="给 <project_dir>/review/<project>_review.xlsx 追加 '视觉索引' Sheet, 带缩略图。",
    )
    p_visuals.add_argument("project_dir", type=Path, help="项目目录")
    p_visuals.add_argument("--xlsx", type=Path, default=None, help="显式指定 xlsx (默认自动查找)")
    p_visuals.add_argument("--quiet", action="store_true", help="静默模式")
    p_visuals.set_defaults(func=_cmd_visuals)

    # doctor
    p_doctor = sub.add_parser(
        "doctor",
        help="检查 project_dir 是否具备生成评审的最小条件",
        description="检查 review.json、raw_assets、已有产物和 external-game 视觉证据是否齐全。",
    )
    p_doctor.add_argument("project_dir", type=Path, help="项目目录")
    p_doctor.set_defaults(func=_cmd_doctor)

    # version
    p_ver = sub.add_parser("version", help="打印版本")
    p_ver.set_defaults(func=_cmd_version)

    return parser


def app(argv: list[str] | None = None) -> int:
    """game-review CLI 入口. pyproject.toml [project.scripts] 指向这里."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(app())
