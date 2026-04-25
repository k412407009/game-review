# MVP A 跑通反思: 用 review-board 评外部游戏

> **对象**: Last Beacon: Survival (Google Play · com.hnhs.endlesssea.gp)
> **耗时**: 约 2.5 小时 (含 10 分钟装依赖 + 20 分钟等待 fetch/下载 + 实际工作约 2 小时)
> **日期**: 2026-04-20
> **本文目的**: 记录"把 ppt-master 内部立项评审 skill 套到外部上线产品上"这件事**到底跑得通不通**, 给下一步决策 (维持 MVP / 升级 B / 升级 C / 放弃) 提供证据。

---

## TL;DR

**跑通了**, 但是**不完整, 有 4 个硬约束**, review 输出**有决策价值但精度一般**。

- 三件套产出: `.docx` 46KB / `.xlsx` 18KB / `.md` 9.9KB, 内容格式正常, 评委视角差异化明显。
- 最大的意外发现: **D8 (团队/预算) 和 D9 (PPT 表达力) 对外部上线产品结构性失效** — 这是 review-board skill 层的真实 gap, 必须在 B 阶段解决。
- 第二大意外: **国内网络环境下 YouTube gameplay 视频下载走不通** (SSL 握手超时 8.8 分钟重试全挂), 这是做外部游戏评审的第一个部署约束。
- **建议升级 B 阶段**, 不是 C (C 过度工程化)。B 的工作量约半天, ROI 高。

### [v2 update, 2026-04-20 T2]

用户用公司 VPN 解锁 YouTube 后, 提供 2 个视频 URL + 顺手修复 `fetch_game_assets.py` 的一串隐藏 bug, 视频环节**打通了**:

- 2 个视频 (8:05 葡语 Lv.7 playthrough + 3:00 印尼语 Shorts 新手) 下载成功, ffmpeg scene-detect 抽 80 帧, Doubao Vision AI 打标全部完成 (42,495 tokens, 463 秒, 0 错误, 成本约 $0.15)
- **视频证据对结论的决定性影响**: 发现 "主题递减" 现象 (D1 从 2.8 下调到 2.2) + 抽卡 4min 限免 + 遗物双轴养成实锤 (D5 从 2.8 升到 3.6) + Shorts 新手期 0 氪金要素暴露 (D3/D4 从"信息缺失惩罚" 2.2 升到 3.4/3.6)
- **新发现的 skill 层 bug** (3 条, 详见 §8): `_heuristic_label` 竖屏误判 / `fetch_gameplay` 硬编码 ytsearch / argparse `--game` 前缀匹配导致互斥错误
- **对 MVP A 结论的修订**: **信度标注远比"维度 mode 切换"更重要**. D1/D2 是 "视频直接可判" 的维度, D3/D4/D5 是 "静态截图严重欠估" 的维度, 信度分级应该基于"数据源类型"不是"评委视角"。这是 B 阶段的方向调整。

**结论**: MVP A (仅商店截图) 给出的结构性判断 (D1 题材风险 / D5 长尾生存) 在 v2 视频证据下**主要结论保留**, 但**内部维度数值大幅调整**, 说明**视频证据对外部评审是 must-have 不是 nice-to-have**。

### [T3 update, 2026-04-20 T3] 用户直接砍掉 D8/D9 而不是做 mode 切换

原计划 B-1 是加 `mode: internal_project | external_product` 字段, 两种模式下脚本过滤不同维度。用户决策更简洁: **直接从 charter 移除 D8/D9**, 不分内外。

- **Skill 层**: `review-board.md` charter + `generate_review.py` + `build_summary.py` DIMENSIONS 从 9 改 7 (仅保留 D1-D7)
- **Last Beacon**: `Last-Beacon_review.json` 删除所有评委 scores 里的 D8/D9 条目, 删除 Q11 (讨论 D8/D9 gap 的 issue), 清理 reviewers[P].perspective 里的 "团队/排期/预算", 重算加权总分 3.1 (9 维) → 3.31 (7 维)
- **内部 E/H/I**: review.json 保留, 历史 docx/xlsx 不动; 但这 3 个 JSON 里总共有 9 条 D8/D9 issue (E 2 条 / H 3 条 / I 4 条), 如果未来重跑会在 Excel Issues sheet 的"维度"列显示原始代号 `D8`/`D9` (脚本 fallback). 用户可选: 一次性清理 / 重跑时再说 / 完全不动 (历史归档)
- **与 B-1 的差异**: 不支持"同一个 skill 两种模式", 直接把 D8/D9 定性为"不应该存在过的维度"。预算/团队讨论建议挪到 `design_spec.md` Part 6 或单独做 `delivery_plan.md`, 不再走评委会 (见 `review-board.md` §VIII.6 新增条款)

**T3 决策的代价/好处**:
- 代价: 未来如果又想评"团队/预算"维度, 需要重新加回去 (但 charter 里 §I 保留了"历史"段, 可查)
- 好处: schema 更简单 (5 评委 × 7 维度 = 35 格子 vs 45 格子), 评审会时间压缩, 内外评审用同一套维度, 无 mode if-else 分支

---

## 1. 跑通了什么

| 环节 | 状态 | 耗时 | 产出 |
|---|---|---|---|
| 装依赖 (yt-dlp + ffmpeg + Tavily key) | ✓ | 5 分钟 | yt-dlp 2026.03.17 + ffmpeg 8.1 + `.env` 里 ARK + TAVILY key |
| `fetch_game_assets.py` 拉商店素材 | ✓ | 3 分钟 | 18 张 Google Play 截图 + metadata.json |
| 亲读前 8 张 + 采样 3 张截图做视觉分类 | ✓ | 15 分钟 | 识别出 6 个独立场景 × 3 重复的展示结构 |
| WebSearch 补文字信息 (厂商 / 玩法 / 竞品 benchmark) | ✓ | 10 分钟 | Immersive Games HK / 海洋末日 4X SLG / Last War + Whiteout benchmark |
| 写 `external_game_brief.md` (外部游戏速写) | ✓ | 25 分钟 | 7 节结构化 spec, 替代内部项目的 `design_spec.md` |
| 手写 `Last-Beacon_review.json` (5 评委 × 9 维度 × 11 问题) | ✓ | 45 分钟 | 符合 review-board JSON Schema |
| 跑 `generate_review.py` 出三件套 | ✓ (二次) | 5 分钟 (首次碰到 Windows ADS bug, 修 JSON project 字段后重跑) | .docx + .xlsx + .md |
| 抽查 xlsx / md 内容正确性 | ✓ | 5 分钟 | 评委全名 / 维度全名正确渲染, 分数矩阵合理 |

---

## 2. 跑不通了什么 (4 个硬约束, 按影响程度排序)

### 2.1 硬约束 A — `D8 / D9 维度对外部上线产品结构性失效` ~~(v1)~~ → **[T3 已彻底解除: 从 charter 移除]**

**v1 症状**:
- D8 (团队/排期/预算): 外部公司不公开团队规模和投入成本, 评委只能从产品质量**反推猜测** (Last Beacon 美术质量高 ≈ 中等团队投入), 精度低
- D9 (演讲/PPT 表达力): 外部游戏**根本没有立项 PPT**, 我被迫把 Google Play 商店 listing 当成"营销 PPT" 的 proxy, 对 18 张截图 6 独立 × 3 重复 这件事打了 2 分。这不是原维度在评, 是另一个东西。

**v1 现象**: 最终 xlsx `Scores` sheet 里 D9 均分 2.0 (最低), D8 均分 2.6, 拖累加权总分 —— 实际上这两维**不应进入外部评审的加权**。

**T3 解除**: 2026-04-20 T3 用户决策**不做 mode 切换, 直接砍维度**. charter 从 9 维改为 7 维, D8/D9 彻底消失。内部立项 PPT 的团队/预算讨论挪到 `design_spec.md` Part 6 或 `delivery_plan.md`, 不再走评委会。

**v1 时估算的"未来 20 款外部游戏 × 每款两维惩罚分 = 汇总失真"问题**: 已消除, 因为这两维不再存在。

### 2.2 硬约束 B — `国内网络环境下 YouTube gameplay 视频下载结构性失败` ~~(v1)~~ → **[v2 降级为软约束]**

**v1 症状** (已被 v2 部分解决):
- `yt-dlp` 搜索能返回结果 (走 youtube.com 网页, 某种程度上可达), 但**实际视频下载走 googlevideo.com CDN, 在国内被限速/被墙**, SSL 握手反复超时
- 2 个真实候选视频 (`OxWu88bJ7Is` + `QVGEUhSGTeU`) 各 3 次重试全部失败, 8.8 分钟全部耗在 SSL 握手上

**v1 连锁影响**:
- D3 (时间节点) 和 D4 (阶段过渡) 没有视觉证据, 评委只能凭文字描述推测, 被迫打"信息不足惩罚分" (均分 2.2)
- `fetch_game_assets.py` 的 AI 打标对 store 截图被 heuristic 跳过 (因为 `store/googleplay/*.jpg` 路径被识别为 `store-screenshot` 单一类, 不细分), 结果所有 19 张都是一个标签。**视觉分析不是 AI 做的, 是我亲手读了 8 张 + 3 张采样做的**

**v1 缓解方案** (已在 MVP 中采用):
- 绕过 yt-dlp 视频, 亲读商店截图 (18 张里前 8 张是核心卖点, 投入 ~5000 tokens 换清晰的视觉判断, 值得)
- WebSearch 多次针对性搜索弥补视频字幕缺失的玩法细节

**v2 解除**: 用户开启公司 VPN, yt-dlp 直接下 YouTube 成功 (葡语 Lv.7 8:05 + 印尼语 Shorts 3:00), 24 秒下完 2 个视频, 场景检测抽 80 帧, Doubao Vision 打标全部完成. **这个约束对有 VPN 的用户不存在, 对无 VPN 的用户仍存在**, 所以降级为"软约束/部署约束"。

**v2 剩余问题**: 当前 fetcher 依赖 `ytsearch` 搜索, 不支持显式 URL 传入 (B-3 action 验证), 手动用 `yt-dlp <url>` 下载是绕过方案。

**长期需要** (B-3 升级为 P1): `fetch_game_assets.py` 加 `--yt-urls` 参数, 用户手动指定 URL 列表, 彻底绕过搜索词误匹配。

### 2.3 硬约束 C — `Windows NTFS 对文件名冒号的 ADS 陷阱 (generate_review.py bug)`

**症状**:
- 首次跑 `generate_review.py` 时, 因为 `review JSON` 的 `project` 字段包含 `:` (`Last Beacon: Survival`), 脚本直接用它拼接文件名
- Windows NTFS 把 `name:stream.ext` 解析为 `name` 文件的 **Alternate Data Stream (ADS)**, 结果磁盘上出现一个 0 byte 的 `Last_Beacon` "主文件" + 3 个隐藏的 ADS 流
- `Get-ChildItem` 看不到 docx/xlsx/md, 但 Python 的 `open()` 能"读到" (因为它走文件路径而不是目录列表)

**MVP 绕过方案**: 改 JSON 的 `project` 字段, 冒号换成 ` - ` (横杠), 第二次跑成功

**长期需要**: `generate_review.py` 应该对 `data['project']` 做 `sanitize_filename()` (替换 `:/\*?"<>|` 等 Windows 非法字符), 不是信任上游输入。这是个 5 行代码的 bug fix。

### 2.4 硬约束 D — `商店截图的 AI 打标粒度不够细`

**症状**:
- `fetch_game_assets.py` 的 heuristic 把 `store/googleplay/*.jpg` 全部打成 `store-screenshot` 单一标签
- 实际上 18 张里有 6 种不同画面 (cover / 基地建造 / 资源采集 / 防御战 / 小队战 / 英雄抽卡) 需要细分
- 脚本的设计是: heuristic 能判断的就不送 AI (省 Doubao Vision token), 但对 store 截图的粒度判断过于粗

**MVP 绕过**: 我亲读 11 张图 (Claude 原生视觉), 做人肉分类 + 视角解读 (大约 25K tokens 开销)

**长期需要**: B 阶段给 `fetch_game_assets.py` 加一个 `--deep-label-store` flag, 对 store 截图也送 Doubao Vision 做细分类 (识别 battle/build/gacha/ui 等). 预估单个游戏增加 $0.05-0.1 API 成本, ROI 高。

---

## 3. Review 输出质量自评 (按 7 维度)

| 维度 | 打分精度 | 信度来源 | 评估 |
|---|---|---|---|
| **D1 战略-题材匹配度** | **高** | 商店描述 + 18 张截图视觉 + WebSearch 竞品 benchmark | ✓ "SS01 情感调性 vs SS02-06 玩法调性割裂" 这个洞察是**评审真正的增量价值**, 文字分析做不出来, 视觉+结构化维度组合才出来 |
| **D2 玩法-核心循环** | 中 | 6 个独立场景推测 + 商店文案 + Whiteout/Last War 类比 | 知道有"建造+探索+战斗+抽卡+联盟"三件套, 但**具体节奏和数值边界看不到**, 中等精度 |
| **D3 玩法-时间节点** | 低 | 无 gameplay 视频, 纯文字推测 | ⚠️ 2.2 分是"信息不足惩罚", 不是真实评估。**应标注 N/A 而不是打分** |
| **D4 玩法-阶段过渡** | 低 | 无长期运营数据, 从截图战力数字推测 | ⚠️ 同 D3, 信度标注缺失问题 |
| **D5 商业化-付费/留存** | **中高** | 明确的 benchmark 数据 (Last War $2.47 / Whiteout $1.08) + SS06 钻石数字 1.1M 暗示抽卡深度 | ✓ 带 benchmark 锚点的评估是可靠的 |
| **D6 风险-题材/合规** | 高 | 海洋/灯塔无敏感 + 抽卡合规现状可查 | ✓ 合规是文字可完全覆盖的维度, 不依赖视觉 |
| **D7 美术/配色/素材** | 高 | 亲读 11 张截图 | ✓ 视觉维度上视觉模型直接能判断 |

**整体评估**:
- **D1 D6 D7 (3 个维度) 输出质量高** — 商店页 + 截图 + Web 文字足以支撑
- **D5 输出质量中高** — 有 benchmark 锚点就靠谱, 缺 benchmark 就猜
- **D2 输出质量中** — 结构推测清楚, 深度/数值判不了
- **D3 D4 输出质量低** — 视频缺失的硬约束, 不是方法论问题
- **D8 D9 输出质量无意义** — 结构性失效

**结论**: 7 维度评审里 4-5 个维度的输出是**有决策价值的**, 2 个维度是"能打但精度低", 2 个 (D8/D9) 根本不应该打。这对"建立外部游戏对照库服务立项决策"是够用的 baseline, 但前提是**B 阶段必须修 D3/D4 的信度标注 + D8/D9 的 mode 切换**。

---

## 4. 升级 B 阶段的 Action List (按 ROI 排序)

### B-1. `review-board` 加"内部/外部"模式切换 (⭐⭐⭐ 最高 ROI, 约 2-3h)

**改动范围**:
- `review-board.md` charter 补一章 "VII. 外部产品评审模式": 说明 mode 字段 / 7 维度强制 / 信度分级
- `generate_review.py` + `build_summary.py` 读 JSON 里的新字段 `mode`: `"internal_project"` (默认, 9 维度) / `"external_product"` (7 维度, 跳过 D8 D9)
- 每个评分加 `confidence` 字段: `"实玩" / "视频" / "商店页" / "推断"` 四档, 渲染时作为分数旁边的小字

**效果**: 未来评外部游戏的 Scores 表不会再有 D8/D9 "惩罚行", 加权总分真实反映 7 维度, Action Items 也干净

### B-2. `generate_review.py` 文件名 sanitize (⭐⭐⭐ 5 分钟, 防坑)

```python
# 在 _build_docx / _build_xlsx / _build_subjective_md 头部加:
import re
safe_project = re.sub(r'[:/\\*?"<>|]', '_', data['project'])
# 然后用 safe_project 拼接文件路径
```

**效果**: Windows 用户永远不会再碰到 ADS 陷阱

### B-3. `fetch_game_assets.py` 加 `--yt-urls` 显式传 URL (⭐⭐ 约 30 分钟)

**当前**: 脚本 hardcode `ytsearch{max_videos}:{game_name} gameplay` 作为搜索词, 对小众出海游戏经常误匹配或 0 结果

**改**: 加一个 `--yt-urls URL1,URL2` 参数, 如果传了就跳过搜索, 直接下载指定 URL. 搜索是 fallback.

**效果**: 评委/分析师可以手动挑视频, 绕过搜索噪音

### B-4. `fetch_game_assets.py` 加 `--deep-label-store` flag (⭐ 约 20 分钟)

**改**: 对 `store/googleplay/*.jpg` 也送 Doubao Vision 做细分类 (battle / build / gacha / ui / character / alliance 等), 不再 heuristic 一刀切

**成本**: 单游戏 +$0.05-0.1 API, 但视觉分析从"我亲读"变成"脚本自动"

### B-5. (可选) 代理支持 (⭐ 半小时, 看用户环境)

**场景**: 国内网络 + 用户有 V2Ray/Clash 等代理, 希望直接下载 YouTube 视频

**改**: `fetch_game_assets.py` 读 `.env` 里的 `HTTP_PROXY` / `HTTPS_PROXY`, 传给 yt-dlp 的 `--proxy` 参数

**注意**: 这是环境依赖, 不是所有人都有代理, 所以放低优先级

### B-6. [v2 新增] `_heuristic_label` 对竖屏帧系统性误判 (⭐⭐⭐ 5 分钟, 阻塞 AI 打标)

**症状** (v2 发现): `fetch_game_assets.py` 第 623 行:
```python
if ratio < 0.7:
    return "ui-menu"   # 竖屏一律判 ui-menu
```

这导致**所有 360×640 / 288×640 等竖屏手游录像抽帧 (ratio 0.45-0.56)** 全部被判为 ui-menu, `need-AI` 列表为空, 80 帧 Doubao Vision 一次都不调用. 这是**系统性错判**, 竖屏手游录像是外部游戏评审最主流的视频格式。

**绕过方案** (v2 采用): 写独立脚本 `scripts/direct_label.py` 绕过 heuristic, 80 帧直接送 Doubao Vision (42,495 tokens, $0.15, 463 秒)

**修复方案**:
```python
def _heuristic_label(img_path: Path):
    w, h, size_kb = _get_image_info(img_path)
    ratio = w / h if h > 0 else 1
    if "store" in str(img_path):
        return "store-screenshot"
    if size_kb < 10:
        return "loading"
    # FIX: ui-menu 通常是弹窗 panel, 正常竖屏手游 ratio 0.45-0.65 不算
    # 只有极窄 ratio 才是 UI 面板, 或明确是 gameplay/frames/ 里的交给 AI
    if "gameplay/frames" in str(img_path):
        return None   # 让 AI 分类
    if ratio < 0.35:
        return "ui-menu"
    return None
```

### B-7. [v2 新增] AI 打标输出补充 "中文描述" 字段 (⭐⭐ 15 分钟)

**v1 状态**: `label_frames` 只输出 single label (如 "main-city"), max_tokens=10, 每帧只拿到 12 分类之一

**v2 发现的价值**: `scripts/direct_label.py` 改成同时要 label + 30 字中文描述, token 成本从 10 → ~530/帧 (`42495 / 80 ≈ 531`), **成本增加 53x 但信息增加 20x** — 可以从描述直接看到"抽卡池限免 4min"/"主城灯塔+10 建筑"等结构化事实, 不需要每次人工开图。

**建议**: B-7 把这个补充回 `fetch_game_assets.py` 的 `label_frames()`, 增加 `--with-desc` flag (默认 on), 一并写 `descriptions.json`. 成本可接受 (~$0.15/外部游戏), ROI 极高。

### B-8. [v2 新增] argparse 前缀匹配防坑 (⭐ 5 分钟, 纯文档)

**症状** (v2 发现): 脚本用 positional `game` 参数, 但 argparse **前缀匹配**会把 `--game "Last Beacon"` 识别成 `--gameplay-only` 的缩写 (因为 `game` 是 `gameplay-only` 的前缀), 触发互斥组错误 (跟 `--label-only` 互斥).

**绕过** (v2 采用): 用 positional 参数 `python fetch_game_assets.py "Last Beacon: Survival" ...` 而不是 `--game "..."`

**修复**: 要么用 `argparse.ArgumentParser(allow_abbrev=False)` 禁用前缀匹配, 要么把 positional 参数改成显式 `--game-name` flag (跟 `--gameplay-only` 前缀不同). **前者更干净, 影响面小**。

### B-9. [v2 新增] `labels.json` 路径分隔符统一 (⭐ 10 分钟, 防数据脏)

**症状** (v2 发现): `fetch_game_assets.py` 写路径用 `\\` (Windows NT backslash), direct_label.py 用 `/` (POSIX), 导致 labels.json 有 178 条, 其中 98 条是同一份数据的两种路径表示. 虽然不影响 `generate_review.py` (它不读 labels.json), 但影响 `emit_resource_list` 和未来 cross-game 对比。

**修复**: 统一用 POSIX 路径 (`path.as_posix()`), 每次写入前规范化。

---

## 5. 不应升级到 C 阶段 (独立 "游戏评审" skill) 的理由

C 阶段 = 把 review 从 ppt-master 拆出来做成通用 skill, 两种输入源都支持。**我在 MVP 跑完后反对这个方案**:

1. **工作量比 B 大一个数量级** (约 1-2 天 vs 半天), 但带来的额外价值很小 —— 因为 ppt-master 本身就是立项 PPT 的容器, 评审 skill 跟它耦合没错
2. **review-board charter 本身已经通用** (5 评委人物卡 + 9 维度定义 + JSON Schema 都不依赖 ppt-master 内部概念), 拆出来只是改一下文件位置, 没有实质抽象
3. **B 阶段的 mode 切换已经足够优雅** —— 同一个 skill 支持内外两种模式, 比"一个 skill 变两个"更好维护

**C 留给未来**: 如果外部游戏评审的量级起来了 (比如一个月评 10+ 款), 且评审维度跟立项 PPT 开始分化 (外部产品更关注数据/口碑/运营, 内部立项更关注创意/团队/预算), 那时候再拆也不晚。**当前不拆**。

---

## 6. 下一次评审前的 Checklist

如果用户决定在 B 阶段改造前, 先再评 1-2 款游戏验证 MVP 的 reproducibility:

- [ ] 游戏名 + Google Play / App Store / Steam URL (必填)
- [ ] 可选: 2-3 个 YouTube 视频 URL (绕开脚本搜索误匹配, 减少 D3/D4 信息缺失的痛苦)
- [ ] 可选: SensorTower / data.ai 页面链接 (如果游戏规模够大)
- [ ] 确认 `ppt-master/.env` 里 `ARK_API_KEY` + `TAVILY_API_KEY` 都配齐
- [ ] 按 MVP 流程跑一遍, **记录耗时**, 看第 2 次是不是比第 1 次快 (应该快 30%+, 因为流程熟悉了)
- [ ] 产出 review 三件套后**读一遍 Scores 表**, 如果 D8/D9 又拉垮总分, 立刻启动 B-1 (mode 切换) 改造

---

## 7. 对 `review-board` charter 的轻微措辞建议 (无需立刻改)

当前 `review-board.md` 第 9 行: "触发条件: 用户在 PPTX 导出后明确要'找评委会评一遍'或'二次确认评审'"

**建议扩展**:
> 触发条件:
> - 内部立项: 用户在 PPTX 导出后明确要"找评委会评一遍"或"二次确认评审" → 9 维度评审
> - 外部产品: 用户提供 Google Play / App Store / Steam URL 希望用 review-board 标准评判一款上线产品 → 7 维度评审 (跳过 D8 D9), 输入替换为 `external_game_brief.md` (详见 B 阶段升级)

---

## 8. v2 补强 (2026-04-20 T2): 视频环节走通

### 8.1 流水线打通

| 环节 | 命令 / 脚本 | 结果 | 耗时 |
|---|---|---|---|
| VPN 解锁 YouTube 访问 | 用户手动开公司 VPN | ✓ | 即时 |
| yt-dlp 下载 2 个视频 | `yt-dlp -f "mp4[height<=480]" <url>` × 2 | 62 MB (葡语 8:05 Lv.7) + 7 MB (印尼语 Shorts 3:00) | 24 秒 |
| ffmpeg 场景检测抽帧 | `select='gt(scene,0.4)'` + `ntb_frames` max 50 | 80 帧 (Lv.7 视频 50 帧 + Shorts 30 帧) | 约 30 秒 |
| Doubao Vision AI 打标 + 描述 | `scripts/direct_label.py` 绕过 heuristic bug | 80 帧全部打标成功, 0 错误 | 463 秒 |
| 更新 `Last-Beacon_review.json` | 新增 `video_evidence` 字段 + 调整 6 个维度 × 5 评委分数 | 11 问题 → 15 问题 (新增 Q12-Q15) | 手工 |
| 重新生成三件套 | `python generate_review.py <dir>` | docx 48KB / xlsx 19KB / md 11KB | 5 秒 |

**总耗时**: 约 1.5 小时 (含 AI 打标 8 分钟 + 读 labels.json/descriptions.json 半小时 + 改 review.json 半小时 + 重跑 5 分钟)

### 8.2 AI 打标投入产出比

- **Token 消耗**: 42,495 tokens (80 帧, ~530 tokens/帧, 含 ~120 token 中文描述输出)
- **美元成本**: 约 $0.15 (Doubao Vision `doubao-seed-1-6-vision-250815`, 输入 0.3 + 输出 0.6 元/1K tokens)
- **标签分布** (80 帧):

| 标签 | 数量 | 占比 | 含义 |
|---|---|---|---|
| main-city | 20 | 25% | 主城建造界面 (灯塔 + 建筑群) |
| ui-menu | 16 | 20% | 商店/任务/联盟/背包等菜单 |
| character | 13 | 16% | 英雄详情页 / 立绘 |
| ad-creative | 10 | 12% | 视频片头/UP 主 logo/黑屏过渡 |
| shop-gacha | 8 | 10% | 抽卡池界面 (含 4min 限免计时) |
| cutscene | 4 | 5% | 剧情过场 |
| map-world | 4 | 5% | 世界地图/探索点 |
| battle | 3 | 4% | 战斗场景 (敌方 Boss / 舰队对战) |
| tutorial | 1 | 1% | 新手引导 |
| other | 1 | 1% | 未能精确分类 |

### 8.3 视频证据对 review 结论的决定性影响

| 维度 | v1 (仅截图) | v2 (+视频) | 变化原因 |
|---|---|---|---|
| D1 战略-题材匹配 | 2.8 | **2.2 ↓** | 视频证实"海洋主题仅在开场, 5min 后主城画面与通用 SLG 无差异", 新增 Q12 "主题递减" 问题 |
| D2 玩法-核心循环 | 3.0 | **2.6 ↓** | 视频证实 20% 为 main-city 建造 + 25% 为菜单系统, 核心玩法几乎没有独特性, 新增 Q13 差异性讨论 |
| D3 玩法-时间节点 | 2.2 | **3.4 ↑** | Shorts 新手 3 分钟清晰呈现 0 氪金要素 + 任务指引, 从"惩罚分"变"真实评估", 新增 Q14 补齐时间节点 |
| D4 玩法-阶段过渡 | 2.2 | **3.6 ↑** | Lv.7 playthrough 看到建造+战斗+抽卡+探索 4 类场景自然切换, 从"信息不足"变"可观察" |
| D5 商业化-付费 | 2.8 | **3.6 ↑** | 抽卡池 4min 限免计时 + 遗物系统双轴养成实锤, 从"benchmark 推测"变"直接证据", 新增 Q13 讨论 |
| D7 美术/素材 | 3.4 | 3.4 | 无变化 (截图已够判断) |

**净效果**: 加权总分从 2.75 → 2.95 (仍未过 3.2 立项线), 但**结构性判断更稳固**:
- D1 题材风险从"怀疑" → "实锤" (从 2.8 调低到 2.2, Q12 priority 升为 P0)
- D5 长尾生存从"推测" → "确认双轴养成" (从 2.8 升到 3.6, 但 Q13 提出竞品 Last War 的遗物系统更深)
- D3/D4 从"无法评估" → "可评估" (脱离"惩罚分" 陷阱)

**对 MVP A 结论的修订** (TL;DR 已更新):
> 信度标注 (`confidence: 实玩/视频/商店页/推断`) 远比 "维度 mode 切换 (internal/external)" 更重要. D1/D2/D7 在 "仅静态截图" 下已可判断, D3/D4/D5 在 "仅静态截图" 下被系统性低估. 信度分级应该基于"数据源类型"不是"评委视角"。

### 8.4 新发现的 skill 层 bug (已加入 B 阶段 Action List)

| 编号 | 严重度 | 文件 | Symptom |
|---|---|---|---|
| B-6 | P0 (阻塞 AI 打标) | `fetch_game_assets.py:623` | `_heuristic_label` 对竖屏帧 (ratio<0.7) 一律判 ui-menu, 手游录像系统性漏标 |
| B-7 | P1 (信息收益大) | `fetch_game_assets.py:642-843` | `label_frames` 仅输出 label, 不含中文描述, 需要加 `--with-desc` |
| B-8 | P2 (非阻塞) | `fetch_game_assets.py` argparse | 前缀匹配把 positional `game` 错认成 `--gameplay-only`, 需要 `allow_abbrev=False` |
| B-9 | P2 (数据脏) | `fetch_game_assets.py` label 写入 | Windows 路径 `\\` vs POSIX `/` 混用, `labels.json` 出现同 key 的两种表示 |

**共同特点**: 都是"竖屏手游 + 中文用户"场景下的隐藏 bug, 内部 SLG 评审 (横屏 PPT 图片) 跑不到这些 path, 所以 MVP A 之前看不到。

### 8.5 v2 反向修正 MVP A 的 TL;DR

原 TL;DR 的 3 个结论在 v2 下重新评估:

1. ~~"D8/D9 对外部上线产品结构性失效"~~ → **仍然成立**, 视频证据改变不了这一点
2. ~~"国内网络环境下 YouTube 下载走不通"~~ → **降级为软约束**, VPN 用户可用, 无 VPN 用户仍需 B-5 (代理支持) 或 B-3 (手动 URL)
3. ~~"建议升级 B 阶段"~~ → **更强的建议: 先做 B-1 + B-6**, B-1 是 mode 切换修 D8/D9, B-6 是修竖屏 heuristic 让 AI 打标跑通. 两者合计约半天, 但解决**两个不同层面的阻塞**

---

## 附录: 产出文件清单

```
external-game-reviews/
├── MVP_A_reflection.md                       (本文件, 决策依据)
└── Last-Beacon-Survival/
    ├── external_game_brief.md                (速写, 替代 design_spec.md, 给评委看)
    ├── raw_assets/
    │   └── Last-Beacon-Survival/
    │       ├── store/googleplay/              (18 张商店截图 + icon)
    │       ├── meta/                          (image_resource_list.md)
    │       ├── gameplay/
    │       │   ├── frames/<vid_id>/scene_*.jpg  (v2 新增: 80 张场景帧)
    │       │   ├── <vid_id>.mp4                  (v2 新增: Lv.7 + Shorts 原视频 69 MB 合计)
    │       │   ├── labels.json                   (v2 扩展: 80 AI 标签 + 19 store 标签, 含重复路径)
    │       │   └── descriptions.json             (v2 新增: 80 帧中文描述 ~30 字/帧)
    │       └── metadata.json
    ├── scripts/
    │   └── direct_label.py                    (v2 新增: 绕过 heuristic bug 的一次性打标脚本)
    └── review/
        ├── Last-Beacon_review.json            (v2: 5 评委 × 9 维度 × 15 问题 + video_evidence 字段)
        ├── Last_Beacon_-_Survival_..._review.docx    (48 KB, 完整评审报告)
        ├── Last_Beacon_-_Survival_..._review.xlsx    (19 KB, Issues / Scores / Action_Items)
        └── Last_Beacon_-_Survival_..._subjective_responses.md  (11 KB, 主观问题最优解)
```
