"""
Review Board · 跨项目评审汇总 (review-summary.md)

读 <projects_root>/<project_dir>/review/*_review.json 全部
产出 <projects_root>/review-summary.md

Usage:
    python skills/ppt-master/scripts/review/build_summary.py <projects_root>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except Exception:
    pass


DIMENSIONS = {
    "D1": "战略-题材匹配度",
    "D2": "玩法-核心循环",
    "D3": "玩法-时间节点",
    "D4": "玩法-阶段过渡",
    "D5": "商业化-付费/留存",
    "D6": "风险-题材/合规",
    "D7": "美术/配色/素材",
}

VERDICT_LABEL = {
    "pass": "✅ PASS",
    "conditional_pass": "⚠️ CONDITIONAL PASS",
    "not_pass": "❌ REJECT",
}

VERDICT_RANK = {"pass": 0, "conditional_pass": 1, "not_pass": 2}


# JSON 内部保留 P/S1/D8 等代号 (机器可读外键), 但所有面向人的产物一律展开成全名。

def _rev_label(rev: dict) -> str:
    """评委显示标签: '资深制作人 (15年)'。"""
    return f"{rev['name']} ({rev['years']}年)"


def _rev_lookup(reviewers: list[dict]) -> dict[str, dict]:
    return {r["id"]: r for r in reviewers}


def _avg_per_dim(scores: dict[str, dict[str, int]]) -> dict[str, float]:
    out = {}
    for d in DIMENSIONS:
        vals = [s.get(d, 0) for s in scores.values()]
        vals = [v for v in vals if v]
        out[d] = round(sum(vals) / len(vals), 2) if vals else 0.0
    return out


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("用法: python build_summary.py <projects_root>")
        return 2
    root = Path(argv[1]).resolve()
    if not root.exists():
        print(f"项目根目录不存在: {root}")
        return 2

    all_data: list[dict[str, Any]] = []
    for proj_dir in sorted(root.iterdir()):
        if not proj_dir.is_dir():
            continue
        review_dir = proj_dir / "review"
        if not review_dir.exists():
            continue
        for j in sorted(review_dir.glob("*_review.json")):
            try:
                d = json.loads(j.read_text(encoding="utf-8"))
                d["__source"] = j
                d["__project_dir"] = proj_dir.name
                all_data.append(d)
                break
            except Exception as e:
                print(f"  警告: {j} 读取失败 → {e}")

    if not all_data:
        print(f"  未找到任何 review.json (扫描: {root})")
        return 2

    print(f"  读到 {len(all_data)} 份 review.json:")
    for d in all_data:
        print(f"    - {d['project']} → {d['__source'].name}")

    # 取第一份 review 里的 reviewers 作为评委会展示 (5 人在所有项目里固定相同)
    reviewers_for_header = all_data[0].get("reviewers", [])
    rev_header = " / ".join(_rev_label(r) for r in reviewers_for_header) if reviewers_for_header else "-"

    lines: list[str] = []
    lines.append("# Review Board · 跨项目评审汇总")
    lines.append("")
    lines.append(f"> 涵盖 {len(all_data)} 个项目, 评委会 5 人: {rev_header}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ===== I. 总体裁决对照 =====
    lines.append("## I. 总体裁决对照")
    lines.append("")
    lines.append("| 项目 | 加权总分 | 裁决 | 复审节点 |")
    lines.append("|---|---|---|---|")
    for d in sorted(all_data, key=lambda x: VERDICT_RANK.get(x["verdict"], 9)):
        lines.append(
            f"| **{d['project']}** | {d['weighted_score']}/5 | "
            f"{VERDICT_LABEL.get(d['verdict'], d['verdict'])} | "
            f"{d.get('next_review', '-')} |"
        )
    lines.append("")

    # ===== II. 7 维度评分纵向对比 =====
    lines.append("## II. 7 维度评分纵向对比")
    lines.append("")
    header = ["维度"] + [d["project"][:18] for d in all_data]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "|".join(["---"] * len(header)) + "|")
    avg_by_proj = {d["project"]: _avg_per_dim(d["scores"]) for d in all_data}
    for dim_id, dim_name in DIMENSIONS.items():
        row = [f"**{dim_name}**"]
        for d in all_data:
            v = avg_by_proj[d["project"]][dim_id]
            mark = ""
            if v <= 3.0:
                mark = " ⚠️"
            elif v >= 4.5:
                mark = " ⭐"
            row.append(f"{v}{mark}")
        lines.append("| " + " | ".join(row) + " |")
    overall_row = ["**加权总分**"] + [f"{d['weighted_score']}" for d in all_data]
    lines.append("| " + " | ".join(overall_row) + " |")
    lines.append("")
    lines.append("> ⚠️ = 该维度均分 ≤ 3.0 需重点回应   ⭐ = 该维度均分 ≥ 4.5 项目亮点")
    lines.append("")

    # ===== III. 共性问题 (跨 ≥2 项目) =====
    lines.append("## III. 共性问题 (≥2 项目都中招, 提到 skill 层迭代)")
    lines.append("")
    dim_lows: dict[str, list[str]] = {}
    for d in all_data:
        dims = avg_by_proj[d["project"]]
        for dim_id, v in dims.items():
            if v <= 3.5:
                dim_lows.setdefault(dim_id, []).append(d["project"])
    common_dims = {k: v for k, v in dim_lows.items() if len(v) >= 2}
    if not common_dims:
        lines.append("(无共性低分维度, 3 项目各有侧重)")
    else:
        lines.append("| 维度 | 命中项目 | 建议 |")
        lines.append("|---|---|---|")
        for dim_id, projs in common_dims.items():
            lines.append(
                f"| **{DIMENSIONS[dim_id]}** | {' / '.join(projs)} | "
                f"建议 ppt-master skill 在 strategist.md 增加该维度专项 checklist |"
            )
    lines.append("")

    # ===== IV. 各项目 P0 清单 =====
    lines.append("## IV. 各项目 P0 必改清单")
    lines.append("")
    has_p0 = False
    for d in all_data:
        p0_issues = [q for q in d["issues"] if q["priority"] == "P0"]
        if not p0_issues:
            lines.append(f"### {d['project']}")
            lines.append("")
            lines.append("✅ 无 P0 项, 可直接进入复审")
            lines.append("")
            continue
        has_p0 = True
        rev_lookup = _rev_lookup(d.get("reviewers", []))
        lines.append(f"### {d['project']} ({len(p0_issues)} 项 P0)")
        lines.append("")
        lines.append("| ID | 评委 | 影响页 | 问题 | 改动建议/最优解 |")
        lines.append("|---|---|---|---|---|")
        for q in p0_issues:
            advice = q.get("suggestion") or q.get("best_answer") or "-"
            advice = advice.replace("\n", " ").replace("|", "\\|")
            question = q["question"].replace("\n", " ").replace("|", "\\|")
            rev = rev_lookup.get(q["reviewer"], {})
            rev_str = _rev_label(rev) if rev else q["reviewer"]
            lines.append(
                f"| {q['id']} | {rev_str} | {q.get('page', '-')} | {question} | {advice} |"
            )
        lines.append("")

    # ===== V. 推进建议 =====
    lines.append("## V. 推进建议")
    lines.append("")
    rank_sorted = sorted(all_data, key=lambda x: (VERDICT_RANK.get(x["verdict"], 9), -float(x["weighted_score"])))
    lines.append("**推荐推进顺序** (从 PPT 最成熟 → 最需返工):")
    lines.append("")
    for i, d in enumerate(rank_sorted, start=1):
        p0_n = len([q for q in d["issues"] if q["priority"] == "P0"])
        lines.append(
            f"{i}. **{d['project']}** — 总分 {d['weighted_score']}/5 / "
            f"裁决 {VERDICT_LABEL.get(d['verdict'], d['verdict'])} / "
            f"P0 共 {p0_n} 项"
        )
    lines.append("")

    # ===== VI. skill 层改进建议 =====
    lines.append("## VI. ppt-master skill 层改进建议")
    lines.append("")
    if common_dims:
        lines.append("基于本轮评审, 建议 skill 在以下方面强化 (减少未来项目同样跌跟头):")
        lines.append("")
        for dim_id, projs in common_dims.items():
            lines.append(
                f"- **{DIMENSIONS[dim_id]}** → "
                f"在 `references/strategist.md` 八问八答里加一项专项校验, 命中项目: {' / '.join(projs)}"
            )
        lines.append("")
    lines.append("- 在 `references/review-board.md` §VIII 加 'verdict 提升路径' 表格 (从 conditional → pass 需要哪些动作)")
    lines.append("- 在 strategist 自查 checklist 里新增 '评委 5 视角扫雷' 条目, 让 design_spec.md 提交前自查")
    lines.append("")

    out_path = root / "review-summary.md"
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  wrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
