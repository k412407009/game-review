# 赛道改造指南_TRACK_ADAPTATION_GUIDE

## 这份文档是干什么的

`game-review` 当前的默认评审框架，是从轻量化 SLG / 模拟经营 / 放置的经验里抽出来的。

如果你要把它改造成：

- 休闲 RPG
- 棋牌 / 卡牌
- 捕鱼

不能只改一句 prompt。要分清楚：

1. **哪些文件定义了评委和评审维度**
2. **哪些文件定义了权重、输出 schema 和文档渲染**
3. **哪些文件定义了外部游戏素材抓取和视觉标签**

---

## 一眼看懂：哪些文件是“必须改”的

### A. 评委、维度、评分逻辑

这些文件是主事实源，赛道一变，优先改这里：

- [`skills/game-review/references/review-board.md`](../skills/game-review/references/review-board.md)
  - 评委 persona
  - D1-D7 含义
  - 输出规范
  - review.json 样例
- [`skills/game-review/SKILL.md`](../skills/game-review/SKILL.md)
  - skill 对外说明
  - 权重说明
  - 模式定义
- [`apps/api/api/ai_stub.py`](../apps/api/api/ai_stub.py)
  - `DIMENSIONS`
  - `CORE_DIMENSIONS`
  - `DIMENSION_WEIGHTS`
  - `REVIEWERS`
  - Compass/stub prompt

### B. 输出 schema 和报表渲染

如果维度数量、命名或字段结构变了，这些必须同步：

- [`apps/api/api/schemas.py`](../apps/api/api/schemas.py)
  - API 层 review schema slim
- [`skills/game-review/scripts/review/generate_review.py`](../skills/game-review/scripts/review/generate_review.py)
  - Word / Excel / Markdown 渲染
- [`skills/game-review/scripts/review/build_summary.py`](../skills/game-review/scripts/review/build_summary.py)
  - 跨项目汇总维度矩阵

### C. 外部游戏素材与视觉标签

如果赛道变化导致“看图重点”变化，这里要改：

- [`apps/api/api/rich_context.py`](../apps/api/api/rich_context.py)
  - `CORE_DIMS_STORE`
  - `CORE_DIMS_VIDEO`
  - 商店页 / 视频证据如何转成评审上下文
- [../../ppt-master/skills/ppt-master/scripts/game_assets/fetch_game_assets.py](../../ppt-master/skills/ppt-master/scripts/game_assets/fetch_game_assets.py)
  - `LABEL_CATEGORIES`
  - `SCENE_QUOTA`
  - 视觉模型分类 prompt
  - `descriptions.json` 输出
- [`skills/game-review/scripts/review/add_visual_sheet.py`](../skills/game-review/scripts/review/add_visual_sheet.py)
  - 视觉索引 Sheet 的展示与 fallback

---

## 哪些文件只是“镜像 / 历史副本”

这些文件也有同样的维度定义，但不是未来改造的主入口：

- [../../ppt-master/skills/ppt-master/references/review-board.md](../../ppt-master/skills/ppt-master/references/review-board.md)
  - 这是 `game-review` charter 的历史副本
- [../../ppt-master/skills/ppt-master/scripts/review/generate_review.py](../../ppt-master/skills/ppt-master/scripts/review/generate_review.py)
- [../../ppt-master/skills/ppt-master/scripts/review/build_summary.py](../../ppt-master/skills/ppt-master/scripts/review/build_summary.py)

如果你已经决定以后统一走 `game-review` repo，这几处可以只做兼容同步；
如果你还要继续支持 `ppt-master` 内部 Step 8 老路径，这几处也得一起改。

---

## 文件级说明：每一层到底存了什么

### 1. 评审 charter 层

`review-board.md` 存的是“制度”：

- 评委是谁
- 每个维度问什么
- 每种问题怎么分 O/S
- 报告里应该出现哪些章节

如果你从轻量 SLG 改到棋牌或捕鱼，这里最先要改的是：

- 评委背景
- 维度定义
- 样例问题
- 样例 `review.json`

### 2. Prompt / 评分层

`ai_stub.py` 存的是“真正驱动评审结果的机器约束”：

- 固定评委列表
- 核心维度优先级
- 维度权重
- Compass prompt 里的输出要求

只改文档、不改这里，LLM 还是会按旧赛道去评。

### 3. 渲染层

`generate_review.py` / `build_summary.py` 存的是“输出时怎么展示 D1-D7”。

如果你只是改评委背景、不改维度数量，改动很小。
如果你把 D1-D7 改成别的维度，或者新增 D8/D9，这层必须一起改。

### 4. 素材证据层

`rich_context.py` 和 `fetch_game_assets.py` 存的是“系统默认认为哪些画面重要”。

当前偏轻量 SLG / 模拟经营的地方主要有两类：

- 商店页更偏向服务 `D1 + D7`
- 视频帧更偏向服务 `D2 + D7`
- 视觉分类里保留了 `battle / main-city / shop-gacha / map-world / tutorial` 等标签

如果你换成棋牌或捕鱼，这里的 quota 和标签体系通常要一起改。

---

## 按赛道拆：通常需要怎么改

### 休闲 RPG

建议优先改：

- `ai_stub.py`
  - 让 `D2` 更关注战斗编队、成长、Build 深度
  - 让 `D3` 更关注新手 30 分钟成长曲线
- `fetch_game_assets.py`
  - 增强 `character`、`battle`、`map-world`
  - 新增或细分 `team-build`、`equipment`、`boss`
- `rich_context.py`
  - 视频证据重点从“泛核心循环”改成“战斗 + 成长 + 美术”

### 棋牌 / 卡牌

建议优先改：

- `review-board.md`
  - 重写 D2/D3/D5 的描述，聚焦单局循环、长线 meta、付费公平性
- `ai_stub.py`
  - 重写评委 persona，减少 SLG/放置语境
- `fetch_game_assets.py`
  - 新增 `battle-board`、`deck-builder`、`pack-opening`、`ranked-ui`
- `add_visual_sheet.py`
  - 视觉索引里建议把“局内画面”和“收藏/卡包画面”分开展示

### 捕鱼

建议优先改：

- `review-board.md`
  - D1 改成题材包装与受众匹配
  - D2 改成射击反馈、目标选择、炮台升级循环
  - D4 改成场景 / Boss / 房间层级推进
- `fetch_game_assets.py`
  - 新增 `fishing-battle`、`boss-wave`、`cannon-upgrade`、`lobby-room`
- `rich_context.py`
  - 视频证据重点改成命中反馈、爆金币、Boss 演出

---

## 推荐改造顺序

1. 先改 [`review-board.md`](../skills/game-review/references/review-board.md)，把新赛道的评委和维度定下来。
2. 再改 [`ai_stub.py`](../apps/api/api/ai_stub.py)，让 API / Compass prompt 真按新规则出分。
3. 再改 `generate_review.py` / `build_summary.py` / `schemas.py`，把输出结构对齐。
4. 最后改 `fetch_game_assets.py` 和 `rich_context.py`，让视觉证据也服务新赛道。

---

## 一个务实原则

如果只是从“轻量 SLG”切到“休闲 RPG”，先改：

- `review-board.md`
- `ai_stub.py`
- `fetch_game_assets.py`

通常就够了。

只有在下面这些情况，才需要继续大改渲染层和 schema：

- 维度数量变化
- `review.json` 字段变化
- 视觉索引需要新增分区
- Web/API 表单要暴露新的赛道配置
