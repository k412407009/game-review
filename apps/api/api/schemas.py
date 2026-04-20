"""Pydantic schemas · API 合约

保持跟 game-review skill 的 review.json schema 一致 (references/review-board.md §VI),
但在 API 层只暴露最小必要字段 — agent 自己组装完整 JSON 的逻辑放 ai_stub.py。
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


# ================= Job lifecycle =================


class JobStage(str, Enum):
    QUEUED = "queued"
    FETCHING = "fetching"       # stage 1: 素材抓取
    SCORING = "scoring"          # stage 2: AI 评审打分
    GENERATING = "generating"    # stage 3: game-review CLI
    PACKAGING = "packaging"      # stage 4: zip 打包
    DONE = "done"
    FAILED = "failed"


class JobMode(str, Enum):
    INTERNAL_PPT = "internal-ppt"
    EXTERNAL_GAME = "external-game"


class JobCreate(BaseModel):
    """POST /jobs 入参 (JSON body).

    注意: 文件上传 (raw_assets.zip / review.json) 走 multipart, 不放这里。
    文件 + 元数据的混合接口 = POST /jobs (multipart/form-data), 见 main.py.
    """

    game_id: str = Field(..., min_length=1, max_length=64, description="项目 id, 安全文件名")
    game_name: str = Field(..., min_length=1, max_length=128)
    mode: JobMode = JobMode.EXTERNAL_GAME
    with_visuals: bool = True
    store_url: str | None = Field(default=None, description="商店页 URL (Phase 3 仅作记录, 不自动抓取)")
    video_url: str | None = Field(default=None, description="gameplay 视频 URL (同上)")
    notes: str | None = Field(default=None, max_length=2000, description="备注 / 上下文")


class JobProgress(BaseModel):
    stage: JobStage
    percent: int = Field(ge=0, le=100)
    message: str = ""
    updated_at: datetime


class JobRecord(BaseModel):
    job_id: str
    created_at: datetime
    request: JobCreate
    progress: JobProgress
    artifacts: list[str] = Field(default_factory=list, description="产物文件名列表 (存在 output/ 目录下)")
    download_url: str | None = None
    error: str | None = None


# ================= game-review schema slim =================
# 仅用于类型标注 / stub, 完整 schema 由 skill 处理


class ReviewerScore(BaseModel):
    D1: int = Field(ge=0, le=5)
    D2: int = Field(ge=0, le=5)
    D3: int = Field(ge=0, le=5)
    D4: int = Field(ge=0, le=5)
    D5: int = Field(ge=0, le=5)
    D6: int = Field(ge=0, le=5)
    D7: int = Field(ge=0, le=5)


class Reviewer(BaseModel):
    id: str
    name: str
    years: int
    background: str = ""
    perspective: str = ""


class ReviewIssue(BaseModel):
    id: str
    priority: Literal["P0", "P1", "P2"]
    dimension: str
    page: str = ""
    question: str
    best_answer: str = ""
    notes: list[str] = Field(default_factory=list)


class ReviewJSON(BaseModel):
    """最小 review.json (用于 stub 生成). skill 允许更多字段, 这里不约束。"""

    project: str
    verdict: Literal["pass", "conditional_pass", "not_pass", "market_observed"]
    weighted_score: float
    review_date: str
    verdict_rationale: str
    next_review: str = "N/A"
    reviewers: list[Reviewer]
    scores: dict[str, ReviewerScore]
    issues: list[ReviewIssue] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict, description="video_evidence / visual_catalog 等")
