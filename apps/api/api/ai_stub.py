"""AI 评审 provider · 优先调用 Compass, 失败时回退到本地 stub。

Phase 3 默认 provider:
  - Compass (`COMPASS_API_KEY`)
  - endpoint: `https://compass.llm.shopee.io/compass-api/v1/chat/completions`

设计目标:
  1. 不改 pipeline / CLI 现有合约
  2. 当 Compass 可用时, 产出真实 `review.json`
  3. 当 key 缺失或上游失败时, 仍回退到 stub 保证链路可跑
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger(__name__)


# 7 维度 (和 skill 定义必须一致)
DIMENSIONS = {
    "D1": "战略-题材匹配度",
    "D2": "玩法-核心循环",
    "D3": "玩法-时间节点",
    "D4": "玩法-阶段过渡",
    "D5": "商业化-付费/留存",
    "D6": "风险-题材/合规",
    "D7": "美术/配色/素材",
}
CORE_DIMENSIONS = ("D1", "D2", "D7")
DIMENSION_WEIGHTS = {
    dim_id: (2.0 if dim_id in CORE_DIMENSIONS else 1.0)
    for dim_id in DIMENSIONS
}

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

VALID_VERDICTS = {"pass", "conditional_pass", "not_pass", "market_observed"}
VALID_PRIORITIES = {"P0", "P1", "P2"}
VALID_ISSUE_TYPES = {"O", "S"}
_DOTENV_LOADED = False


def _load_dotenv_if_present() -> None:
    """读取当前项目目录或其父目录中的 `.env` 到进程环境.

    优先级:
      1. 已存在的环境变量
      2. 当前工作目录向上搜索到的 `.env`
      3. 当前文件所在目录向上搜索到的 `.env`
    """

    global _DOTENV_LOADED
    if _DOTENV_LOADED:
        return

    search_roots = [Path.cwd(), Path(__file__).resolve().parent]
    seen: set[Path] = set()

    for root in search_roots:
        for base in [root, *root.parents]:
            if base in seen:
                continue
            seen.add(base)
            env_path = base / ".env"
            if not env_path.exists():
                continue

            for raw_line in env_path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                if not key or key in os.environ:
                    continue
                if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
                    value = value[1:-1]
                os.environ[key] = value
            break

    _DOTENV_LOADED = True


def _today() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")


def _base_external_game_fields(
    *,
    mode: str,
    store_url: str | None,
    video_url: str | None,
    raw: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if mode != "external-game":
        return {}

    video_evidence = raw.get("video_evidence") if isinstance(raw, dict) else None
    visual_catalog = raw.get("visual_catalog") if isinstance(raw, dict) else None

    if not isinstance(video_evidence, dict):
        video_evidence = {
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

    if not isinstance(visual_catalog, dict):
        visual_catalog = {"store": []}

    return {
        "video_evidence": video_evidence,
        "visual_catalog": visual_catalog,
    }


def _fallback_stub_review(
    *,
    project_id: str,
    project_name: str,
    mode: str,
    store_url: str | None,
    video_url: str | None,
    notes: str | None,
    reason: str,
    extra_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    log.warning(
        "使用本地 stub 生成 review.json (project=%s, mode=%s): %s",
        project_id,
        mode,
        reason,
    )

    scores: dict[str, dict[str, int]] = {}
    for rev in REVIEWERS:
        scores[rev["id"]] = {d: 3 for d in DIMENSIONS}

    stub = {
        "project": project_name,
        "verdict": "conditional_pass",
        "weighted_score": 3.00,
        "review_date": _today(),
        "verdict_rationale": (
            "当前请求未成功调用 Compass，已回退到本地占位评审。"
            f"\n原因: {reason}"
            f"\nmode: {mode}"
            f"\nstore_url: {store_url or '(未提供)'}"
            f"\nvideo_url: {video_url or '(未提供)'}"
            f"\nnotes: {notes or '(无)'}"
        ),
        "next_review": "N/A",
        "reviewers": REVIEWERS,
        "scores": scores,
        "issues": [
            {
                "id": "Q01",
                "reviewer": "P",
                "type": "S",
                "priority": "P1",
                "dimension": "D1",
                "page": "(待补)",
                "question": "当前报告使用了本地占位评审，是否需要补充真实项目资料后二次生成？",
                "subjective_position": "在证据不足时，不建议直接把占位结论当作立项结论使用。",
                "best_answer": "先补全商店页、视频、玩法节点和商业化信息，再重新运行 Compass 评审。",
                "talking_points": [
                    "确认 .env 中已配置 COMPASS_API_KEY",
                    "补充 store_url / video_url / notes 可显著提升评审质量",
                ],
                "notes": [],
            }
        ],
        "highlights": ["已保住端到端流水线可用，报告链路未中断"],
        "risks": ["当前 issues / scores 为占位结论，不能替代真实 LLM 评审"],
    }
    stub.update(
        _base_external_game_fields(
            mode=mode,
            store_url=store_url,
            video_url=video_url,
            raw=extra_fields,
        )
    )
    return stub


def _normalize_reviewer_id(value: Any) -> str | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None

    for rev in REVIEWERS:
        if raw == rev["id"]:
            return rev["id"]

    folded = raw.lower().replace(" ", "")
    aliases = {
        "producer": "P",
        "资深制作人": "P",
        "战略策略": "S1",
        "题材策略": "S1",
        "战略专家": "S1",
        "玩法系统": "S2",
        "玩法策划": "S2",
        "用户运营": "O1",
        "ltv": "O1",
        "投放运营": "O2",
        "买量运营": "O2",
    }
    for alias, target in aliases.items():
        if alias.lower().replace(" ", "") in folded:
            return target

    for rev in REVIEWERS:
        if rev["name"] in raw:
            return rev["id"]

    return None


def _normalize_dimension(value: Any) -> str | None:
    if value is None:
        return None
    raw = str(value).strip()
    if raw in DIMENSIONS:
        return raw

    for dim_id, dim_name in DIMENSIONS.items():
        if dim_name in raw or raw in dim_name:
            return dim_id
    return None


def _coerce_score(value: Any, default: int = 3) -> int:
    try:
        score = int(round(float(value)))
    except (TypeError, ValueError):
        score = default
    return max(1, min(5, score))


def _normalize_scores(raw_scores: Any) -> dict[str, dict[str, int]]:
    normalized: dict[str, dict[str, int]] = {}

    for rev in REVIEWERS:
        rev_raw = raw_scores.get(rev["id"], {}) if isinstance(raw_scores, dict) else {}
        rev_scores: dict[str, int] = {}
        for dim_id in DIMENSIONS:
            value = rev_raw.get(dim_id) if isinstance(rev_raw, dict) else None
            rev_scores[dim_id] = _coerce_score(value)
        normalized[rev["id"]] = rev_scores

    return normalized


def _normalize_text_list(value: Any, *, fallback: list[str], limit: int = 5) -> list[str]:
    if not isinstance(value, list):
        return fallback
    items = [str(item).strip() for item in value if str(item).strip()]
    return items[:limit] or fallback


def _normalize_issue(issue: Any, idx: int) -> dict[str, Any] | None:
    if not isinstance(issue, dict):
        return None

    reviewer = _normalize_reviewer_id(issue.get("reviewer")) or REVIEWERS[idx % len(REVIEWERS)]["id"]
    dimension = _normalize_dimension(issue.get("dimension")) or list(DIMENSIONS)[idx % len(DIMENSIONS)]
    issue_type = str(issue.get("type", "O")).upper()
    if issue_type not in VALID_ISSUE_TYPES:
        issue_type = "O"

    priority = str(issue.get("priority", "P1")).upper()
    if priority not in VALID_PRIORITIES:
        priority = "P1"

    question = str(issue.get("question", "")).strip()
    if not question:
        question = f"请补充 {DIMENSIONS[dimension]} 相关论证与证据。"

    normalized: dict[str, Any] = {
        "id": f"Q{idx + 1:02d}",
        "reviewer": reviewer,
        "type": issue_type,
        "priority": priority,
        "dimension": dimension,
        "page": str(issue.get("page", "(未标注)")).strip() or "(未标注)",
        "question": question,
        "notes": [
            str(item).strip()
            for item in issue.get("notes", [])
            if str(item).strip()
        ]
        if isinstance(issue.get("notes"), list)
        else [],
    }

    if issue_type == "O":
        suggestion = str(issue.get("suggestion", "")).strip()
        if not suggestion:
            suggestion = f"围绕 {DIMENSIONS[dimension]} 补一段更可执行的论证与行动项。"
        normalized["suggestion"] = suggestion
    else:
        subjective_position = str(issue.get("subjective_position", "")).strip()
        best_answer = str(issue.get("best_answer", "")).strip()
        talking_points_raw = issue.get("talking_points", [])
        if not subjective_position:
            subjective_position = "现有信息不足，建议先补证据再做更强判断。"
        if not best_answer:
            best_answer = "当前最优答法应先承认信息不足，再明确下一轮验证计划。"
        talking_points = (
            [str(item).strip() for item in talking_points_raw if str(item).strip()]
            if isinstance(talking_points_raw, list)
            else []
        )
        normalized["subjective_position"] = subjective_position
        normalized["best_answer"] = best_answer
        normalized["talking_points"] = talking_points[:3]

    return normalized


def _normalize_issues(raw_issues: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_issues, list):
        raw_issues = []

    issues = []
    for idx, issue in enumerate(raw_issues):
        normalized = _normalize_issue(issue, idx)
        if normalized is not None:
            issues.append(normalized)

    if issues:
        return issues[:30]

    return [
        {
            "id": "Q01",
            "reviewer": "P",
            "type": "O",
            "priority": "P1",
            "dimension": "D2",
            "page": "(待补)",
            "question": "当前输入信息较少，核心循环与留存钩子的论证不够充分。",
            "suggestion": "补充核心玩法 5min/15min/30min 节点、长期目标与商业化闭环。",
            "notes": [],
        }
    ]


def _compute_weighted_score(scores: dict[str, dict[str, int]]) -> float:
    weighted_total = 0.0
    total_weight = 0.0
    for rev_scores in scores.values():
        for dim_id, dim_score in rev_scores.items():
            weight = DIMENSION_WEIGHTS.get(dim_id, 1.0)
            weighted_total += dim_score * weight
            total_weight += weight
    if total_weight <= 0:
        return 3.0
    return round(weighted_total / total_weight, 2)


def _normalize_verdict(raw_verdict: Any, weighted_score: float) -> str:
    verdict = str(raw_verdict or "").strip()
    if verdict in VALID_VERDICTS:
        return verdict
    if weighted_score >= 4.2:
        return "pass"
    if weighted_score >= 3.0:
        return "conditional_pass"
    return "not_pass"


def _extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if not stripped:
        raise ValueError("Compass 返回空内容")

    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", stripped, flags=re.S)
    if fence:
        stripped = fence.group(1).strip()

    try:
        obj = json.loads(stripped)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", stripped):
        try:
            obj, _ = decoder.raw_decode(stripped[match.start():])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj

    raise ValueError("无法从 Compass 响应中提取 JSON 对象")


def _compass_config() -> dict[str, Any]:
    _load_dotenv_if_present()
    return {
        "api_key": os.environ.get("COMPASS_API_KEY", "").strip(),
        "base_url": os.environ.get(
            "COMPASS_BASE_URL",
            "https://compass.llm.shopee.io/compass-api/v1",
        ).rstrip("/"),
        "model": os.environ.get("COMPASS_MODEL", "compass-max").strip() or "compass-max",
        "timeout_seconds": float(os.environ.get("COMPASS_TIMEOUT_SECONDS", "120")),
        "max_tokens": int(os.environ.get("COMPASS_MAX_TOKENS", "3072")),
        "temperature": float(os.environ.get("COMPASS_TEMPERATURE", "0.25")),
    }


def _build_compass_messages(
    *,
    project_name: str,
    mode: str,
    store_url: str | None,
    video_url: str | None,
    reference_url: str | None,
    notes: str | None,
) -> list[dict[str, str]]:
    reviewers_block = "\n".join(
        f"- {rev['id']}: {rev['name']} ({rev['years']}年) | {rev['perspective']}"
        for rev in REVIEWERS
    )
    dimensions_block = "\n".join(
        f"- {dim_id}: {dim_name}"
        for dim_id, dim_name in DIMENSIONS.items()
    )

    system = (
        "你是资深游戏评审委员会秘书，负责把评委会讨论整理成 machine-readable 的 review.json。"
        "必须只输出一个 JSON object，不要输出 markdown、解释、代码块。"
        "不要捏造具体市场数据、留存率、ROI 或审批结论；信息不足时明确写“不足/待验证”。"
        "issues 必须使用 reviewer id (P/S1/S2/O1/O2) 和 dimension id (D1-D7)。"
        "问题类型 O 需要 suggestion；问题类型 S 需要 subjective_position、best_answer、talking_points。"
        "scores 要有区分度，不要全 3 分或全 4 分。"
        "核心维度是 D1/D2/D7，必须优先拉开这三个维度的分差，不要把它们做成同质化中性分。"
    )

    user = f"""
请基于以下项目资料，生成适配 game-review CLI 的 review.json。

项目:
- project: {project_name}
- mode: {mode}
- store_url: {store_url or "(未提供)"}
- video_url: {video_url or "(未提供)"}
- reference_url: {reference_url or "(未提供)"}
- notes: {notes or "(无)"}

固定评委:
{reviewers_block}

评审维度:
{dimensions_block}

核心维度:
- D1: 战略-题材匹配度
- D2: 玩法-核心循环
- D7: 美术/配色/素材
- verdict、weighted_score、issues 的优先判断都应先围绕 D1/D2/D7，再看其余维度

输出要求:
- verdict: pass / conditional_pass / not_pass 三选一；证据很弱时默认 conditional_pass
- weighted_score: 1.00-5.00
- review_date: 使用 "{_today()}"
- highlights: 3-5 条
- risks: 3-5 条
- issues: 15-20 条，尽量覆盖 5 位评委，每位 3-4 条
- 客观问题 type="O"；主观问题 type="S"
- page 字段若无明确页码，可写 "Store Page" / "Gameplay Video" / "(待补)"，不要留空

JSON schema:
{{
  "project": "{project_name}",
  "verdict": "conditional_pass",
  "weighted_score": 3.6,
  "review_date": "{_today()}",
  "verdict_rationale": "一句到三句中文总结",
  "next_review": "可写 N/A 或具体复审建议",
  "reviewers": {json.dumps(REVIEWERS, ensure_ascii=False)},
  "scores": {{
    "P": {{"D1": 2, "D2": 3, "D3": 3, "D4": 3, "D5": 3, "D6": 3, "D7": 2}},
    "S1": {{"D1": 2, "D2": 3, "D3": 3, "D4": 3, "D5": 3, "D6": 3, "D7": 2}},
    "S2": {{"D1": 3, "D2": 2, "D3": 3, "D4": 3, "D5": 3, "D6": 3, "D7": 3}},
    "O1": {{"D1": 3, "D2": 3, "D3": 3, "D4": 3, "D5": 2, "D6": 3, "D7": 3}},
    "O2": {{"D1": 2, "D2": 3, "D3": 3, "D4": 3, "D5": 3, "D6": 3, "D7": 2}}
  }},
  "highlights": ["..."],
  "risks": ["..."],
  "issues": [
    {{
      "id": "Q01",
      "reviewer": "P",
      "dimension": "D2",
      "type": "O",
      "priority": "P1",
      "page": "Store Page",
      "question": "问题原文",
      "suggestion": "可执行建议"
    }},
    {{
      "id": "Q02",
      "reviewer": "S1",
      "dimension": "D6",
      "type": "S",
      "priority": "P1",
      "page": "Gameplay Video",
      "question": "问题原文",
      "subjective_position": "评委个人倾向",
      "best_answer": "当前方案的最优辩护",
      "talking_points": ["答辩点 1", "答辩点 2"]
    }}
  ]
}}

再次强调:
- 只输出 JSON object
- reviewers 必须保留固定 5 人且字段完整
- D1/D2/D7 不能机械给同一分；如果自动抓到商店页/视频证据，应优先把分歧体现在这三项
- 若资料不足，允许保守判断，但不要写成空数组或空字符串
""".strip()

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _call_compass_review(
    *,
    project_name: str,
    mode: str,
    store_url: str | None,
    video_url: str | None,
    reference_url: str | None,
    notes: str | None,
) -> dict[str, Any]:
    cfg = _compass_config()
    if not cfg["api_key"]:
        raise RuntimeError("COMPASS_API_KEY 未配置")

    payload = {
        "model": cfg["model"],
        "messages": _build_compass_messages(
            project_name=project_name,
            mode=mode,
            store_url=store_url,
            video_url=video_url,
            reference_url=reference_url,
            notes=notes,
        ),
        "temperature": cfg["temperature"],
        "max_tokens": cfg["max_tokens"],
    }
    headers = {"Authorization": f"Bearer {cfg['api_key']}"}
    timeout = httpx.Timeout(cfg["timeout_seconds"], connect=15.0)

    with httpx.Client(timeout=timeout) as client:
        resp = client.post(f"{cfg['base_url']}/chat/completions", headers=headers, json=payload)
        resp.raise_for_status()

    body = resp.json()
    content = body["choices"][0]["message"]["content"]
    return _extract_json_object(content)


def _normalize_review_json(
    raw: dict[str, Any],
    *,
    project_name: str,
    mode: str,
    store_url: str | None,
    video_url: str | None,
    extra_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    scores = _normalize_scores(raw.get("scores"))
    weighted_score = _compute_weighted_score(scores)
    verdict = _normalize_verdict(raw.get("verdict"), weighted_score)

    highlights = _normalize_text_list(
        raw.get("highlights"),
        fallback=["核心卖点与长期留存论证仍有提升空间，但结构化评审已可落地。"],
    )
    risks = _normalize_text_list(
        raw.get("risks"),
        fallback=["现有资料偏少，结论对商店页和视频素材依赖较高。"],
    )

    verdict_rationale = str(raw.get("verdict_rationale", "")).strip()
    if not verdict_rationale:
        verdict_rationale = (
            f"综合 5 位评委的 7 维度评分，加权均分为 {weighted_score}/5。"
            "当前建议先按有条件通过处理，并围绕低分维度补充证据与修订方案。"
        )

    normalized = {
        "project": str(raw.get("project") or project_name).strip() or project_name,
        "verdict": verdict,
        "weighted_score": weighted_score,
        "review_date": str(raw.get("review_date") or _today()),
        "verdict_rationale": verdict_rationale,
        "next_review": str(raw.get("next_review") or "N/A").strip() or "N/A",
        "reviewers": REVIEWERS,
        "scores": scores,
        "issues": _normalize_issues(raw.get("issues")),
        "highlights": highlights,
        "risks": risks,
    }
    normalized.update(
        _base_external_game_fields(
            mode=mode,
            store_url=store_url,
            video_url=video_url,
            raw={**raw, **(extra_fields or {})},
        )
    )
    return normalized


def generate_stub_review(
    *,
    project_id: str,
    project_name: str,
    mode: str = "external-game",
    store_url: str | None = None,
    video_url: str | None = None,
    reference_url: str | None = None,
    notes: str | None = None,
    extra_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """生成 `review.json`.

    优先走 Compass；如果缺 key 或上游失败，则自动回退到本地 stub，避免中断 pipeline。
    """

    try:
        raw = _call_compass_review(
            project_name=project_name,
            mode=mode,
            store_url=store_url,
            video_url=video_url,
            reference_url=reference_url,
            notes=notes,
        )
        normalized = _normalize_review_json(
            raw,
            project_name=project_name,
            mode=mode,
            store_url=store_url,
            video_url=video_url,
            extra_fields=extra_fields,
        )
        log.info(
            "Compass 评审成功 (project=%s, model=%s, weighted_score=%.2f)",
            project_id,
            _compass_config()["model"],
            normalized["weighted_score"],
        )
        return normalized
    except Exception as exc:
        log.exception("Compass 评审失败，回退到本地 stub (project=%s)", project_id)
        return _fallback_stub_review(
            project_id=project_id,
            project_name=project_name,
            mode=mode,
            store_url=store_url,
            video_url=video_url,
            notes=notes,
            reason=f"{type(exc).__name__}: {exc}",
            extra_fields=extra_fields,
        )


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
