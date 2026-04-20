# Review Board — Step 8 二次确认评审 (PPT 完工后专用)

> 此 spec 定义 PPT 导出完成后的"评委会评审"阶段, 是 ppt-master skill 的 Step 8 (Post-export review)。
> 触发条件: 用户在 PPTX 导出后明确要"找评委会评一遍"或"二次确认评审"。
> 输出: 每个项目 3 件套 (`.docx` + `.xlsx` + `subjective_responses.md`) + 1 份跨项目汇总 `review-summary.md`。

---

## I. 评委会人物卡 (5 人, 固定)

| 代号 | 角色 | 工龄 | 背景 | 评审视角 |
|---|---|---|---|---|
| **P** | 资深制作人 | 15 年 | 主导过 3 款放置/SLG 上线 (其中 1 款全球流水 8 位数), 现任研发负责人 | **立项可行性** + **整体节奏** + **商业终局** |
| **S1** | 战略专家 · 题材策略 | 12 年 | 用户研究 + 题材立项咨询出身, 服务过腾讯/网易/米哈游 | **题材匹配度** + **用户画像** + **题材风险/合规** + **赛道竞品** |
| **S2** | 战略专家 · 玩法系统 | 10 年 | 系统策划 + 核心循环设计, 主刀过 2 款月活千万级放置游戏 | **核心循环可行性** + **数值边界** + **玩法粘性** + **长留存设计** |
| **O1** | 运营 · 用户运营 / LTV | 6 年 | 大 R 玩家维护 + 留存优化 | **留存钩子密度** + **付费节点合理性** + **情感链接** + **新手 7 日转化** |
| **O2** | 运营 · 投放 / CPM | 8 年 | TA / Tencent Ads / FB Ads 跨平台投放 | **投放素材兼容度** + **CPM 预算可承担性** + **题材变现天花板** + **品类用户重叠** |

> 历史 (2026-04-20 前) 评委 P 视角含 "团队/排期/预算", 并设有 D8 (团队/排期/预算) 与 D9 (PPT 表达力) 两个维度。因为这两维对外部上线产品结构性失效 (见 external-game-reviews/MVP_A_reflection.md §2.1), 也对内部立项评审意义不大 (预算和 PPT 表达力是流程问题不是产品问题), 2026-04-20 T3 正式从评委会 charter 移除。

---

## II. 评审维度 (7 项 · 每项 1–5 分)

| 维度 ID | 名称 | 主问 |
|---|---|---|
| **D1** | 战略 - 题材匹配度 | S1 主, P 副 |
| **D2** | 玩法 - 核心循环 | S2 主, P 副 |
| **D3** | 玩法 - 时间节点 (5min/15min/30min/1h/2h/4h/Day1→Day2) | S2 主, O1 副 |
| **D4** | 玩法 - 阶段过渡 (放置→沉浸→指挥→外扩) | S2 + P 主 |
| **D5** | 商业化 - 付费/留存 | O1 主, P 副 |
| **D6** | 风险 - 题材/合规 | S1 主, P 副 |
| **D7** | 美术/配色/素材 | P 主, S1 副 |

**打分规则**: 1=灾难 / 2=严重不足 / 3=可接受需补 / 4=优秀 / 5=拔尖

---

## III. 问题分类与处理

每个评委问 **3–6 个问题**, 共 **15–30 个问题/项目**。每个问题有两个属性:

### 属性 1: 客观/主观

- **O (Objective)** — 有明确的改动建议, 在 PPT/文档/数值上可执行
  → 必须给出: 改动位置 (页号/章节) + 改动建议 + 优先级
- **S (Subjective)** — 主观, 业内无统一答案
  → 必须给出: 评委倾向回答 + **当前 PPT 方案的最优解辩护理由** (帮策划/制作人在评委面前 hold 住)

### 属性 2: 优先级

| 优先级 | 含义 | 修订动作 |
|---|---|---|
| **P0** | 立项被否或评委一票否决高风险 | **PPT 终稿前必改** |
| **P1** | 不改会被严重 challenge, 但不至于否决 | **下一次评审前补** |
| **P2** | nice-to-have / 加分项 | **下版迭代再说** |

---

## IV. 输出物规范

每个项目的 `review/` 目录下产出 3 件套:

### 1. `<project>_review.docx` (评审报告 · 给评委 + 制作人)

```
封面: 项目名 / 评委会 5 人 / 评审日期 / 整体打分 / 一句话裁决
执行摘要: 7 维度雷达图描述 + 高低分维度 + 3 大风险 + 3 大亮点
逐评委意见: 每位评委一节, 含评分表 + 3-6 个问题 + 改动建议
修订总览 (Action Items): 按 P0/P1/P2 分组, 列出具体修订条目
最终裁决: 通过 / 有条件通过 / 不通过 + 复审节点
```

### 2. `<project>_review.xlsx` (问题清单 · 给执行)

3 个 sheet:
- **`Issues`**: 每行 1 个问题 (评委 / 维度 / 类型 O/S / 优先级 / 问题描述 / 改动建议 / 影响页号)
- **`Scores`**: 5 评委 × 7 维度 打分矩阵 + 平均分 + 加权分
- **`Action_Items`**: 按 P0/P1/P2 分组的可执行清单 (含 owner / 预估工时 / 截止节点)

### 3. `<project>_subjective_responses.md` (主观问题最优解 · 给制作人)

仅含 S 类问题, 每条:
```
## Q-NN: <问题原文>
**评委**: <代号> · **维度**: <Dx> · **优先级**: <P0/P1/P2>
**评委倾向**: <评委自己的看法>
**最优解辩护**: <PPT 当前方案为什么也合理>
**口径建议**: <制作人答辩话术 1-3 句>
```

---

## V. 跨项目汇总: `review-summary.md`

放在 `F:\Git\ppt-master\projects\` 根目录, 包含:
- 3 项目整体打分对照表 (7 维度 × 3 项目)
- 共性问题 (3 项目都中招的) → 提到 skill 层迭代
- 单项目独有 P0 问题清单
- 推荐推进顺序 (哪个先复审 / 哪个可直接立项)

---

## VI. 工具链

| 工具 | 用途 |
|---|---|
| `python skills/ppt-master/scripts/review/generate_review.py <project_dir>` | 读 `review/<project>_review.json` → 生成 docx + xlsx + subjective_responses.md |
| `python skills/ppt-master/scripts/review/build_summary.py <projects_root>` | 读多个项目的 `<project>_review.json` → 生成跨项目汇总 |

### `<project>_review.json` Schema

```json
{
  "project": "E_TCG卡店帝国",
  "verdict": "conditional_pass",
  "weighted_score": 4.05,
  "review_date": "2026-04-20",
  "reviewers": [
    {"id": "P", "name": "资深制作人", "years": 15, "background": "...", "perspective": "..."},
    {"id": "S1", "name": "战略专家·题材", ...}
  ],
  "scores": {
    "P":  {"D1":4, "D2":4, "D3":5, "D4":4, "D5":3, "D6":4, "D7":4},
    "S1": {...}, "S2": {...}, "O1": {...}, "O2": {...}
  },
  "highlights": [
    "封面闪卡金 + Pokemart 暖色配色高级",
    "Slide 11 头 30min 8 钩子密集, 抗早期流失设计扎实"
  ],
  "risks": [
    "Slide 22 节奏曲线峰值过密, 第 2 周可能审美疲劳",
    "L5 PVE-SLG 三阶段商业进阶 ROI 模型缺乏一手数据支撑"
  ],
  "issues": [
    {
      "id": "Q01",
      "reviewer": "P",
      "dimension": "D2",
      "type": "O",
      "priority": "P1",
      "page": "Slide 13",
      "question": "升级店面图 45° 俯视角好看, 但实际 mobile 玩家在小屏看清楚吗?",
      "suggestion": "加一张同视角的 mobile 全屏截图对照, 证明 UI 可读"
    },
    {
      "id": "Q07",
      "reviewer": "S1",
      "dimension": "D6",
      "type": "S",
      "priority": "P1",
      "page": "Slide 27",
      "question": "TCG 题材在国内审批合规上有没有未抽到稀有卡 = 赌博的争议?",
      "subjective_position": "我个人认为这是潜在 P0 风险, 应在 Slide 27 单开半页讨论",
      "best_answer": "TCG Card Shop Sim 的'抽包'是模拟经营, 玩家本人不是 gambler 而是店主, 法律定性更接近放置经营, 不触发 G 类版号。但需准备版号沟通文档作为附件",
      "talking_points": [
        "对标 Steam 上 TCG Card Shop Sim 已上架 PRC 版无问题",
        "我们的玩家身份是店主, 卖卡 ≠ 抽卡赌博",
        "已咨询合规团队, 准备好版号沟通材料"
      ]
    }
  ]
}
```

---

## VII. 评审流程 (走完 1 个项目)

1. **读源材料**: `design_spec.md` (Part 5 重点), `<project>.md` (源文档), exports 下的 PPTX 文件名
2. **写 JSON**: 按 §VI Schema 填 `<project_root>/review/<project>_review.json`
3. **跑脚本**: `python skills/ppt-master/scripts/review/generate_review.py <project_root>` → 自动产 3 件套
4. **可选 verify**: 用 PowerPoint / WPS 打开 `<project>_review.docx` 看排版
5. **汇总**: 3 项目都跑完后, `python skills/ppt-master/scripts/review/build_summary.py projects/` → `review-summary.md`

---

## VIII. 红线 / 注意

1. **不要凭空捏造数据**: 评委的所有"基准对比" (类如"对标某游戏 D1 留存 35%") 必须用 design_spec / 源文档里出现过的数据, 不能臆造
2. **主观问题必须有 best_answer**: 不能只列问题不给答案, 那是甩锅
3. **每个评委 3-6 问, 不少于 15 / 不超过 30**: 太少就不严肃, 太多评审会变成走过场
4. **打分要有差异**: 5 个评委 × 7 维度 = 35 个格子, 全 4 分或全 5 分等于没评; 应该有 1-2 个 2 分或 3 分体现真实争议
5. **verdict 三选一**: `pass` / `conditional_pass` / `not_pass`, 没有"通过但需要重做"这种含糊词
6. **维度历史变更**: 2026-04-20 T3 将 D8 (团队/排期/预算) 与 D9 (PPT 表达力) 从 charter 移除, 现仅评 D1-D7。历史 review.json 里保留的 D8/D9 分数和 issue 不再被脚本读取, 但向后兼容; 如需保留团队/预算讨论, 建议挪到 `design_spec.md` 的 Part 6 (交付计划) 或单独做 `delivery_plan.md`, 不再走评委会。
