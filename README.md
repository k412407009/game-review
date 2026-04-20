# game-review

> 独立的 **"游戏评审委员会"** skill, 从 [ppt-master](https://github.com/...) 剥离 (2026-04-21)。
>
> 以 5 位评委 (制作人 / 战略-题材 / 战略-玩法 / 运营-LTV / 运营-投放) × 7 维度 (题材 / 核心循环 / 时间节点 / 阶段过渡 / 商业化 / 风险合规 / 美术) 的结构, 把游戏评审变成可复现的结构化产出 (Word + Excel + Markdown).

## 为什么拆出来

- **ppt-master 的本职是 "生成 PPT"**, review 是它的收尾步骤, 耦合进主 skill 后, 外部游戏评审 (不生成 PPT 的场景) 变得难用
- 本 skill 支持 **两种输入源** (立项 PPT / 外部游戏), 未来扩展到 CLI / Web 服务更干净
- 详见 `docs/roadmap.md`

## 快速开始

```bash
# 1. 装依赖 (python 3.10+)
pip install python-docx openpyxl Pillow

# 2. 准备一份 review.json (schema 见 skills/game-review/references/review-board.md §VI)
#    放到 <your_project>/review/<your_project>_review.json

# 3. 内部 PPT 评审 (默认)
python skills/game-review/scripts/review/generate_review.py <your_project>

# 3'. 外部游戏评审 (+ 视觉索引 Sheet)
python skills/game-review/scripts/review/generate_review.py <your_project> \
    --mode external-game --with-visuals
```

产出:
- `<project>/review/<project>_review.docx` — 完整评审报告
- `<project>/review/<project>_review.xlsx` — Issues / Scores / (视觉索引) / Action_Items
- `<project>/review/<project>_subjective_responses.md` — 主观问题最优解

## 两种模式

| 模式 | 典型场景 | 输入 | 推荐 flag |
| --- | --- | --- | --- |
| `internal-ppt` (默认) | 内部立项评审, 已经做完 PPT | 自己写的 review.json | 无 |
| `external-game` | 外部上线游戏 / 竞品分析 / 投资决策 | ppt-master 的 `fetch_game_assets` 产出 + 自己写的 review.json | `--with-visuals` |

## 目录结构

```
game-review/
  README.md                         你正在看的这个
  docs/
    roadmap.md                      从 skill → CLI → Web SaaS 的渐进路径
  skills/
    game-review/
      SKILL.md                      skill 门面 (给 AI agent 看)
      references/
        review-board.md             评审委员会 charter (评委/维度/评分刻度/JSON schema)
      scripts/
        review/
          generate_review.py        主入口: JSON → docx/xlsx/md (+可选视觉索引)
          build_summary.py          跨项目汇总
          add_visual_sheet.py       给 xlsx 追加视觉索引 Sheet
```

## 为什么要 review.json 而不是 PPT

**评审流程是 "人 / AI 讨论 → 结构化数据 → 落地文档"**:

```
评委会讨论 (AI 模拟 or 真人)
  ↓
review.json  ← 结构化的讨论结果, agent 能生成, 人能读懂
  ↓
Word / Excel / Markdown  ← 给非技术读者看的标准产出
```

这套设计让打分逻辑跟文档生成解耦 — 今天换 Word 模板 / 换 Excel 列序, 不影响打分; 明天换评委 / 换维度, 只改 JSON schema。

## 典型使用链路

```
[场景 A] 立项 PPT 评审:
  ppt-master (Step 1-7 生成 PPT)
    → ppt-master (Step 8 评委讨论, 填 review.json)
    → game-review (本 skill, 生成三件套)

[场景 B] 外部游戏评审:
  fetch_game_assets (收集商店/视频/买量素材)
    → agent 填 review.json (含 video_evidence 和 visual_catalog)
    → game-review --mode external-game --with-visuals (生成四件套)
```

## 文档

- [`docs/roadmap.md`](docs/roadmap.md) — 从 skill → CLI → Web SaaS 的渐进路径 + 成本/时间估算
- [`skills/game-review/SKILL.md`](skills/game-review/SKILL.md) — AI agent 读的 skill 门面
- [`skills/game-review/references/review-board.md`](skills/game-review/references/review-board.md) — 评审委员会 charter (完整定义)

## License

MIT (本 skill 及其 scripts). 外部素材收集工具 (ppt-master 的 fetch_game_assets) 产出的视频帧 / 截图的版权归原游戏发行商所有, 本 skill 只生产 **评论性分析报告**, 建议遵循所在司法管辖区的 "合理使用 / fair use" 边界。
