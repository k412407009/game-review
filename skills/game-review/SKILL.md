---
name: game-review
description: >
  AI-driven game review committee for mobile / SLG / simulation game projects.
  Generates Word + Excel + Markdown review reports with 5 expert personas scoring
  7 dimensions. Supports two modes: internal-ppt (立项 PPT 评审) and
  external-game (外部已上线游戏评审, 含商店素材 + gameplay 视频关键帧视觉索引).
  Use when user asks to "游戏评审", "review 这款游戏", "外部游戏评审",
  "立项评审", "评委会 Review", or mentions "game-review", "review-board".
---

# Game Review Skill

> 独立的 "游戏评审委员会" skill, 从 ppt-master 剥离 (2026-04-21)。
> 输入: 一份结构化的 `<project>_review.json` (评委分数 / 问题清单 / 主观答复)。
> 输出: Word 完整报告 + Excel 3-4 sheet + Markdown 主观最优解。

## 使命与边界

**这个 skill 做什么**:
- 把评委会的 **评分 / 问题 / 讨论** 结构化成 JSON
- 根据 JSON 生成规范化的 3 件套 (可选 4 件套) 评审产出

**这个 skill 不做什么**:
- 不负责 **收集素材** (→ 由 `ppt-master/scripts/game_assets/fetch_game_assets.py` 负责)
- 不负责 **生成 PPT** (→ 由 `ppt-master` 负责)
- 不负责 **打分本身** (评委角色由 agent 扮演, 写进 JSON 后才由本 skill 落地)

## 两种模式

| 模式 | `--mode` | 数据来源 | 典型场景 |
| --- | --- | --- | --- |
| 立项 PPT 评审 | `internal-ppt` (默认) | ppt-master 产出 PPT + 策划文档 | 内部立项 8 Confirmation 后的第 2 次 Review |
| 外部游戏评审 | `external-game` | 外部游戏商店 / gameplay 视频 / 投放素材 | CP 研究 / 竞品分析 / 投资决策 |

两种模式的打分框架一致 (7 维度 D1-D7), 输出格式一致。差异在于:
- `external-game` 建议开 `--with-visuals`, 自动嵌入商店截图 + 视频关键帧缩略图到 Excel
- `internal-ppt` 一般不需要 `--with-visuals`, 除非项目目录里也收集了参考素材

## 核心脚本

| 脚本 | 作用 | 关键参数 |
| --- | --- | --- |
| `scripts/review/generate_review.py` | 主入口: JSON → docx/xlsx/md 三件套 | `project_dir --mode {internal-ppt,external-game} --with-visuals` |
| `scripts/review/add_visual_sheet.py` | 追加 "视觉索引" Excel Sheet (内嵌缩略图) | `project_dir [--xlsx path] [--quiet]` |
| `scripts/review/build_summary.py` | 跨项目汇总评审结果 (Word + Excel + Markdown) | `batch_dir` (多个 project_dir 的父目录) |

## 输入 JSON Schema

完整 schema 见 `references/review-board.md §VI`。速查:

```json
{
  "project": "项目名 (带括号/路径友好, 生成文件名用)",
  "verdict": "pass | conditional_pass | not_pass | market_observed",
  "weighted_score": 3.31,
  "review_date": "YYYY-MM-DD",
  "verdict_rationale": "评审结论原因 (长文本, 支持换行)",
  "next_review": "下次 review 时间 / N/A",
  "reviewers": [
    {"id": "P", "name": "资深制作人", "years": 15, "background": "...", "perspective": "..."},
    ...
  ],
  "scores": {
    "P":  {"D1": 2, "D2": 3, "D3": 4, "D4": 4, "D5": 4, "D6": 4, "D7": 4},
    ...
  },
  "issues": [
    {"id": "Q01", "priority": "P0", "dimension": "D1",
     "page": "对应页面/画面", "question": "问题描述",
     "best_answer": "评委会最优解", "notes": [...]}
  ],
  "video_evidence": {   // external-game 模式选填
    "sources": [...],
    "frame_analysis": {
      "key_scenes_human_read": [
        {"frame": "scene_1281 (长视频 43s)", "content": "...",
         "dims_affected": ["D1", "D5"]}
      ]
    }
  },
  "visual_catalog": {   // external-game 模式选填, 给 --with-visuals 用
    "store": [
      {"code": "封面图", "path": "raw_assets/game/store/googleplay/screenshot_01.jpg",
       "label": "封面图 (cover)", "desc": "..."}
    ]
  }
}
```

## 快速用法

**推荐先装 CLI** (Phase 2, 2026-04-21 起可用):

```bash
# 在 game-review repo 根目录
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

# 检查
game-review --help
game-review version
```

### 内部 PPT 评审 (默认模式)

```bash
# 1. 用 agent 帮你填写 review.json (放到 <project>/review/<project>_review.json)
# 2. 生成三件套
game-review review <project_dir>
# 旧接口 (仍然支持, 不需装 CLI):
#   python skills/game-review/scripts/review/generate_review.py <project_dir>

# 产出:
#   <project>/review/<project>_review.docx
#   <project>/review/<project>_review.xlsx
#   <project>/review/<project>_subjective_responses.md
```

### 外部游戏评审 (含视觉索引)

```bash
# 1. 用 ppt-master 的 fetch_game_assets 收集商店/视频素材
# 2. 用 agent 填 review.json (含 video_evidence / visual_catalog)
# 3. 生成 4 件套
game-review review <project_dir> --mode external-game --with-visuals

# 旧接口:
#   python skills/game-review/scripts/review/generate_review.py <project_dir> \
#       --mode external-game --with-visuals

# 产出: 在 3 件套基础上, xlsx 多一个 "视觉索引" sheet
#   商店截图区: 按 visual_catalog.store 或 auto-scan raw_assets/*/store/
#   视频关键帧区: 按 video_evidence.key_scenes_human_read 的 scene id 反查
#   desc 缺失时会回退到 raw_assets/*/gameplay/descriptions.json
```

### 跨项目汇总

```bash
# 当有多个 project 各自跑完 review 后
game-review summary <batch_dir>
# 旧接口:
#   python skills/game-review/scripts/review/build_summary.py <batch_dir>
# batch_dir 下应该有若干个 <project>/review/*_review.json
```

### 单独追加视觉索引 Sheet (高级)

```bash
game-review visuals <project_dir> [--xlsx path/to/report.xlsx]
```

常见用法: 已经跑过一次 review 但没开 `--with-visuals`, 想在不重跑业务的情况下补视觉索引。

### `raw_assets` 保留规则

外部游戏评审如果要可复现, 不要只保存最终 `docx/xlsx/md`。至少保留:

- `raw_assets/<game>/store/`
- `raw_assets/<game>/gameplay/frames/`
- `raw_assets/<game>/gameplay/labels.json`
- `raw_assets/<game>/gameplay/descriptions.json`
- `raw_assets/<game>/metadata.json`

否则 `--with-visuals` 只能复现文字结构, 无法复现缩略图。

## 依赖

- Python 3.10+
- `python-docx` (Word 生成)
- `openpyxl` (Excel 生成)
- `Pillow` (PIL, 缩略图压缩, 仅 `--with-visuals` 需要)

安装:
```bash
pip install python-docx openpyxl Pillow
```

或读 `<repo_root>/requirements.txt` (如果这个 skill 被 vendored 进其他工程)。

## 7 维度说明

完整定义 (含权重、评分刻度、问题分类标准) 见 `references/review-board.md`。

| 维度 | 中文名 | 权重 |
| --- | --- | --- |
| D1 | 战略-题材匹配度 | 20% |
| D2 | 玩法-核心循环 | 20% |
| D3 | 玩法-时间节点 | 10% |
| D4 | 玩法-阶段过渡 | 10% |
| D5 | 商业化-付费/留存 | 20% |
| D6 | 风险-题材/合规 | 10% |
| D7 | 美术/配色/素材 | 10% |

## 历史沿革

- **2026-04-20 T1**: review 功能作为 ppt-master "Step 8 二次确认评审" 诞生, 评委 5 人 × 9 维度
- **2026-04-20 T3**: 用户要求移除 D8 (团队/排期/预算) 和 D9 (PPT 表达力), 改为 7 维度
- **2026-04-21**: 首次用于外部游戏 (Last Beacon: Survival) MVP A, 证明框架通用
- **2026-04-21**: 脱 ppt-master 独立化成 `game-review` skill (本 skill), 加 `--mode` 和 `--with-visuals`
- **2026-04-21**: Phase 2 CLI 打包完成 — `pyproject.toml` + entry point `game-review` + subcommands `review / summary / visuals / version`, `pip install -e .` 可装, 用 Last Beacon 做过一次 md/docx 字节级回归 (通过)

## 已知 Gap / TODO

1. `--mode` 目前只是元信息标签, 未来应该驱动 **不同权重模板** (例如 external-game 加重 D5 权重)
2. `visual_catalog.store` 的 schema 建议未来内化到 `review-board.md §VI`
3. `add_visual_sheet` 目前只管 store + video, 未来可以加 **投放素材** (ad-creatives) 分区
4. ~~没有 CLI 安装~~ → **已完成 (Phase 2, 2026-04-21)**. 下一阶段是 Phase 3 Web MVP (见 `docs/roadmap.md`)
