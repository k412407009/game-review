"""AI 评审 stub · 生成占位 review.json

**Phase 3 重要说明 (请起床后先读这段)**

这里只是 stub, 用固定 5 评委 + 中性评分 (全 3 分) + 占位文本, 目的是让 Pipeline 端到端能跑通。
真实的 AI 评审必须接真实 LLM (OpenAI / Anthropic / Gemini 等), 参考:
  - skills/game-review/references/review-board.md §V (评委角色定义 + prompt)
  - 5 评委视角打分 + 列问题 + 给最优解

接真实 LLM 时需要 (由你拍板):
  1. 选 provider: OpenAI 4o / Claude Sonnet 4.5 / DeepSeek-R1 / 自建... (建议先 OpenAI, 便宜稳)
  2. 密钥放 .env (OPENAI_API_KEY=..., 不要 commit)
  3. 把下面 `_generate_stub_review()` 替换为真实调用 (见 TODO 注释)

Phase 3 跑通 stub → Phase 3 末尾替换成真实 LLM → Phase 4 多租户时再做 prompt 优化
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


# 7 维度 (和 skill 定义必须一致)
DIMENSIONS = ["D1", "D2", "D3", "D4", "D5", "D6", "D7"]

# 5 评委 (和 skill 定义必须一致)
REVIEWERS = [
    {
        "id": "P",
        "name": "资深制作人",
        "years": 15,
        "background": "大厂 SLG / 模拟经营 / 放置 项目监制",
        "perspective": "战略 - 题材匹配度 / 核心循环 / 阶段过渡 / 风险合规 总把关",
    },
    {
        "id": "S1",
        "name": "战略策略",
        "years": 12,
        "background": "品类定位 + 差异化赛道",
        "perspective": "D1 题材匹配度, D6 风险合规",
    },
    {
        "id": "S2",
        "name": "玩法系统",
        "years": 10,
        "background": "核心循环 + 时间节点 + 阶段过渡",
        "perspective": "D2 核心循环, D3 时间节点, D4 阶段过渡",
    },
    {
        "id": "O1",
        "name": "用户运营",
        "years": 8,
        "background": "LTV / 付费点 / 留存曲线",
        "perspective": "D5 商业化 (LTV/ARPU/ARPPU 视角)",
    },
    {
        "id": "O2",
        "name": "投放运营",
        "years": 8,
        "background": "买量素材 + 美术选材 + CPA",
        "perspective": "D5 商业化 (买量成本视角), D7 美术/素材",
    },
]


def generate_stub_review(
    *,
    project_id: str,
    project_name: str,
    mode: str = "external-game",
    store_url: str | None = None,
    video_url: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """产生一份占位 review.json (全 3 分中性).

    TODO (Phase 3 接真实 LLM 时需要替换这个函数):
      1. 用 prompt 让 LLM 分别模拟 5 评委视角
      2. 输出 5 × 7 的 scores 矩阵
      3. 生成 P0/P1/P2 问题清单 + 最优解
      4. 计算 weighted_score + 给 verdict (pass/conditional_pass/not_pass)
      5. 如果 mode=external-game, 可选地让 LLM 读 store_url / video_url 产出 video_evidence

    返回的 dict 会被 pipeline 写成 <project>_review.json, 交给 game-review CLI 消费。
    """
    log.warning(
        "AI stub 生成 review.json (project=%s, mode=%s) — 产物是中性占位, "
        "非真实评审. 接真实 LLM 见 ai_stub.py 注释.",
        project_id, mode,
    )

    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    scores: dict[str, dict[str, int]] = {}
    for rev in REVIEWERS:
        scores[rev["id"]] = {d: 3 for d in DIMENSIONS}

    stub = {
        "project": project_name,
        "verdict": "conditional_pass",
        "weighted_score": 3.00,
        "review_date": now,
        "verdict_rationale": (
            "⚠️ 这是 AI stub 占位评审, 未接入真实 LLM。"
            f"\n  mode: {mode}"
            f"\n  store_url: {store_url or '(未提供)'}"
            f"\n  video_url: {video_url or '(未提供)'}"
            f"\n  notes: {notes or '(无)'}"
            "\n\n请接真实 LLM 后覆盖此评审。详见 apps/api/api/ai_stub.py."
        ),
        "next_review": "N/A",
        "reviewers": REVIEWERS,
        "scores": scores,
        # issue schema (CLI 硬依赖: reviewer + type + 对应 type 的字段):
        #   type="S" (主观): 必需 best_answer, 可选 subjective_position / talking_points
        #   type="O" (客观): 必需 suggestion
        "issues": [
            {
                "id": "Q01",
                "reviewer": "P",
                "type": "S",
                "priority": "P1",
                "dimension": "D1",
                "page": "(占位)",
                "question": "⚠️ AI stub 占位问题 — 请替换为真实 LLM 输出.",
                "subjective_position": "资深制作人倾向: 等接入真实 LLM 后重新评审.",
                "best_answer": "参考 apps/api/api/ai_stub.py 顶部注释, 接 LLM 后真实评审自动生成.",
                "talking_points": [
                    "当前 stub 产物仅用于端到端 pipeline 验证",
                    "接 LLM 后 5 评委各自独立打分 + 提问",
                ],
                "notes": [],
            }
        ],
        "highlights": ["(AI stub 占位) 接入真实 LLM 后自动提取亮点"],
        "risks": ["(AI stub 占位) 接入真实 LLM 后自动提取风险"],
    }

    if mode == "external-game":
        stub["video_evidence"] = {
            "sources": (
                [{"type": "video", "url": video_url}] if video_url else []
            )
            + (
                [{"type": "store", "url": store_url}] if store_url else []
            ),
            "frame_analysis": {
                "key_scenes_human_read": [],
            },
        }
        stub["visual_catalog"] = {
            "store": [],
        }

    return stub


def write_review_json(target_dir: Path, data: dict[str, Any], game_id: str) -> Path:
    """把 review 数据写到 <target_dir>/review/<game_id>_review.json.

    target_dir 是 game-review CLI 期待的 project_dir 根.
    """
    review_dir = target_dir / "review"
    review_dir.mkdir(parents=True, exist_ok=True)
    out_path = review_dir / f"{game_id}_review.json"
    out_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return out_path
