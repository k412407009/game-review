# 游戏评审 SaaS 化设计梳理 (v2)

> 回答用户的"我能不能把这个评审做成一个用户填链接、等结果的网站"问题。
> 不是立刻动手建网站, 是先把【可行性 / gap / 路径 / 成本 / 风险】全讲清楚, 让决策有依据。
>
> 编写日期: 2026-04-20 (v1, Last Beacon MVP A 后), 2026-04-21 (v2, Phase 1 完成后加"已拍板"章节)
> 作者: PPT Master 评委会 (Claude Opus 4.7 操盘, 丁亮拍板)

## 更新日志

- **v1 (2026-04-20)**: 初稿。基于 Last Beacon MVP A 结果写了 10 章可行性梳理。
- **v2 (2026-04-21)**: 用户 4 问 4 答拍板方向 + Phase 1 (C 方案) 完成。新增:
  - § 0.5 用户已拍板决策 (Q1-Q4 答案 + 路线解读)
  - § 6.1 Phase 1 完成明细 (game-review skill 独立化成果 + 验证数据)
  - § 10 大幅扩写, 把"ABC 串行"具体化为可执行的 2 周 action list

---

## 0. TL;DR (给忙人看)

| 问题 | 答案 |
| --- | --- |
| 能做吗? | **能**。核心能力 (抓素材 / AI 打分 / 出报告) 都是 API 驱动, 没有不可迁移的技术。 |
| 现在做到了什么程度? | **Skill 形态**, 已从 ppt-master 独立成 `game-review` skill (2026-04-21 完成 Phase 1)。离 "用户打开网页填链接等结果" 还有 ~2 周全栈工程。 |
| 最大 gap 是什么? | 不是 AI 能力, 是 **异步任务编排 + 视频获取稳定性 + 多租户 + 成本控制**。 |
| 最大风险是什么? | **视频抓取的合规/稳定性** (YouTube/Bilibili 都有反爬 + TOS 灰区), 以及 **AI API 月度消耗** (单单 Last Beacon MVP A 就烧了 $0.3 左右, 量级放大后能失控)。 |
| 推荐路径 | Phase 1 ✅ (skill 独立化, 半天) → Phase 2 (CLI 打包, 半天) → Phase 3 (单用户 Web MVP, 3-5 天) → Phase 4 (多租户 SaaS, 2-3 周)。**不要跳过 Phase 1**。 |
| 现在的位置 | Phase 1 ✅ 完成 (2026-04-21)。下一步: 冲 Phase 2-3 (见 § 10 本周 action)。 |

---

## 0.5 用户已拍板决策 (v2 新增)

2026-04-21 用户通过 4 问 4 答完成方向选型:

| 决策点 | 选项 | 解读 |
| --- | --- | --- |
| **Q1 目标边界** | **B) 先自用, 好用再对外** | 精益路线, 不急于商业化承诺 |
| **Q2 时间投入** | **B) 5-10 小时/周** | 中等投入, 能做 Phase 3, Phase 4 要咬牙 |
| **Q3 用户信号** | **C) 3-5 个行业内人主动问过** | 有真实 PMF 信号, 不是空想 |
| **Q4 团队状况** | **A) 独立开发** | Bus factor = 1, Phase 4 难度放大 |

**总体定位**: **精益独立开发 + 隐藏版 Phase 3 内测** 路线。

**关键策略**:
- 不挂 landing page 不做公开宣传, 直接把 Phase 3 Web URL 发给那 3-5 个问过的人
- 用真实使用数据 (不是问卷) 决定要不要冲 Phase 4
- Phase 4 触发条件 (3 条必须同时满足):
  1. Week 4 内测人里至少 **3 人实际跑完了一份报告** (不是注册看看就走)
  2. 至少 **1 人** 明确说 "我愿意付钱继续用"
  3. 你每周投入能稳定上到 **10h+**

**独立开发者要避的 5 个坑**:
1. ❌ 不要一次性冲 Phase 4 (独立开发最大死法)
2. ❌ 不要优化不存在的规模 (3 个用户别想多租户)
3. ❌ 不要自己写队列 (用 Trigger.dev / Cloudflare Queues)
4. ❌ 不要追求完美 UI (shadcn/ui 默认组件就够)
5. ❌ 不要早早谈钱 (先让人真用起来, 再想定价)

---

## 1. 从 "Skill" 到 "Web 服务" 的本质差异

这一节最重要 — 搞清楚两者的边界, 后面的一切设计都顺了。

| 维度 | 现在 (Skill 形态) | 目标 (Web 服务) |
| --- | --- | --- |
| **入口** | Cursor 对话框, 告诉 Claude "评一下 Last Beacon" | 浏览器, 用户填表单点 "开始分析" |
| **执行者** | Claude Opus 4.7 (或 Codex, GPT-5) 作为 "操盘手", 调用脚本 | 后端服务 + LLM API (无人类级 agent) |
| **编排** | Agent 自主决策 (装 yt-dlp? 跑 ffmpeg? 修 heuristic?) | 必须固定 pipeline, 失败点提前兜底 |
| **耗时** | 30-90 分钟 (agent + 人 watching) | 同步 < 30 秒响应 / 异步 10-30 分钟后台跑 |
| **输入** | 自由文本 + 文件路径 + agent 理解意图 | 严格结构化表单 (store URL / video URL / PDF) |
| **输出** | 3 件套 (Word/Excel/MD) + 旁白解读 | 网页报告 + 下载包 + 可分享链接 |
| **用户** | 1 个 (你自己) | 多租户 (N 个用户同时在跑) |
| **成本承担** | 你个人 ($20/月 Cursor + API) | 你出钱给每个用户跑, 或用户付费 |
| **故障处理** | Agent 自己 retry, 或你介入 | 必须有队列 / 重试 / 告警 / 客服 |
| **数据隔离** | 无 (你一个人) | 必须 (用户 A 看不到用户 B 的报告) |
| **合规/法务** | 自己用, 灰区可接受 | 面向公众, 得考虑 TOS / 版权 / 隐私 |

**关键洞察**: 你不是在 "把 skill 搬到网页", 你是在 **重新造一个产品**, skill 只贡献了 20-30% 的"核心评分逻辑"。剩下 70% 是工程化 + 产品化。

---

## 2. 用户故事 (User Journey)

> 假设用户是 **游戏制作人 / CP 研究员 / 投资人**, 非技术背景。

### 2.1 核心场景

```
[用户] 我想了解 "Last Beacon Survival" 这款游戏
  ↓
[网站] 
  输入框 1: Google Play / App Store / Steam 链接 (必填)
  输入框 2: YouTube / Bilibili gameplay 视频链接 (选填, 最多 3 个)
  输入框 3: 参考文章/报告链接 (选填, 最多 5 个)
  输入框 4: 重点关注维度 (多选: 题材/玩法/商业化/美术/...)
  输入框 5: 对标产品 (选填, 例如 Last War / Whiteout)
  [开始分析] 按钮
  ↓
[后台] (10-30 分钟)
  Step 1  爬商店页面 (名称/截图/评分/描述/下载量)     30 秒
  Step 2  下载视频 + ffmpeg 抽帧 (每视频 ~40 帧)      3-5 分钟/视频
  Step 3  AI 对所有帧打标签 (Doubao Vision 或 GPT-4V) 5-10 分钟
  Step 4  提取关键帧 + 汇总 (LLM summarize)          2-3 分钟
  Step 5  跨源搜竞品 benchmark (Tavily)              1-2 分钟
  Step 6  模拟评委会 (5 角色 × 7 维度评分)            3-5 分钟 (LLM)
  Step 7  出 3 件套 + 视觉索引                      30 秒
  ↓
[用户] 收到邮件: "你的报告已经好了 → 点这里看"
  ↓
[报告页]
  - 结论卡片 (评级/加权分/核心风险)
  - 维度雷达图 + 评委分歧
  - 视觉索引 (商店图/视频关键帧, 嵌缩略图 + AI 标签)
  - 问题清单 (P0/P1/P2 + 评委主观最优解)
  - 下载 Word/Excel/Markdown
  - 分享链接 (公开/私有)
```

### 2.2 边缘场景 (必须设计)

| 场景 | 系统应该怎么办 |
| --- | --- |
| 视频下不下来 (YouTube 限区域) | 要么转用户上传本地文件, 要么失败时给明确错误 + 建议对策 |
| 商店链接挂了 (404) | 失败, 给错误 + 退款/退积分 |
| AI 打标超额预算 | 降级 (只取 20 帧) 或排队等其它用户 |
| 视频太长 (2 小时) | 强制截断前 30 分钟 + 给用户提示 |
| 游戏是某些敏感题材 | 明确拒绝 + 说明原因 |
| 用户传了盗版游戏截图 | 拒绝, 提示上传官方商店链接 |
| 同一游戏 24 小时内重复分析 | 直接返回缓存报告 + 给用户选 "强制刷新" |

---

## 3. 架构设计 (3 档位)

设计成 3 档并不是为了堆方案, 而是因为 **每一档对应不同的商业阶段 + 不同的投入上限**。

### 3.1 Lite (MVP, 单用户/小团队)

**适用场景**: 你一个人用, 或者给 3-5 个朋友试用, 没有付费。

```
Browser (Next.js 14 App Router)
  ↓ form submit (POST)
API Layer (Next.js API Routes 或 FastAPI)
  ↓ trigger background task
Pipeline (单进程 Python, 调 skill 代码)
  ├─ Tavily API  (web content)
  ├─ yt-dlp      (video download)
  ├─ ffmpeg      (frame extract)
  ├─ Doubao Vision API (label)
  ├─ OpenAI / Claude API (LLM 评分)
  └─ python-docx / openpyxl (出报告)
  ↓ 写盘
File Storage (本地 ./reports/ 或 Vercel Blob)
  ↓ 用户查
Report Page (Next.js, 读报告 HTML/JSON 渲染)
```

**数据库**: 用 Supabase Postgres (免费层) 或 SQLite + 一个 reports 表
**部署**: Vercel (前端) + Render / Railway (后端 + Python worker)
**月成本**: ~$30-80 (AI API 不算)

**不足**:
- 任务队列是 "单进程跑" → 同时 3 个人发请求就排队
- 失败不能重试
- 没有 rate limit → 被人滥用就烧爆你的 API
- 无多租户 (看得到别人的报告)

**适合**: 给自己用的 "小工具", 或 demo 版本

---

### 3.2 Pro (多租户 SaaS, 10-1000 用户)

**适用场景**: 开始收费了, 真有一群用户在用。

```
Browser + Mobile Web (Next.js 14)
  ↓ Auth (Clerk / Auth0)
API Gateway (Vercel / Cloudflare Workers)
  ↓ 
Task Queue (Celery + Redis / BullMQ / Trigger.dev)
  ↓ dispatch
Worker Pool (3-10 个 Python 进程, 按负载伸缩)
  ├─ 视频子池 (专门处理 yt-dlp + ffmpeg, CPU/带宽密集)
  ├─ AI 子池 (调 LLM, 串 rate limit)
  └─ 报告生成池 (纯 CPU, 快)
  ↓
Storage
  ├─ Postgres (Supabase / Neon) — 元数据
  ├─ S3 / R2 — 视频帧 / 报告文件
  └─ Redis — 缓存 (同游戏 24h 内复用)
  ↓
Billing (Stripe)
  ├─ 免费层: 1 份/月
  ├─ Pro: $29/月 → 20 份/月
  └─ 企业: $299/月 → 无限量 + 私有化
  ↓
Monitoring
  ├─ Sentry (错误追踪)
  ├─ Datadog / OpenTelemetry (性能)
  └─ Slack / 邮件告警 (任务失败/预算超额)
```

**额外组件**:
- **Rate Limit**: 按用户 / 按 IP, 防刷
- **Cost Guard**: 单任务预算上限 (例如 $2), 超了自动降级
- **Cache Layer**: 同一游戏 24 小时内结果复用 (省钱)
- **Admin Dashboard**: 你能看到所有任务状态 / 总消耗
- **Email / Webhook**: 任务完成通知

**月固定成本**: ~$200-500 (不含 AI API)
**AI API 成本**: 按每任务 $0.5-2 估, 1000 任务/月 = $500-2000

**技术栈建议**:
- 前端: Next.js 14 + Tailwind + shadcn/ui + React Query
- 后端: **Python FastAPI** (跟现有 skill 代码同语言, 无迁移成本) + Celery
- 任务队列: Celery + Redis
- 数据库: Supabase Postgres + S3 兼容 (R2)
- Auth: Clerk (最省事) 或 Supabase Auth
- 支付: Stripe
- 部署: 后端在 Fly.io / Railway / Render, 前端在 Vercel

---

### 3.3 Ent (企业版, 可选)

**适用场景**: 你哥们工作室 / 腾讯 / 网易 要买, 或发行商要私有化部署。

**加什么**:
- **SSO** (SAML / Okta / Azure AD 对接)
- **私有化部署** (Docker Compose / Helm Chart, 客户自己的云)
- **自定义维度** (不用默认的 7 维, 可以定义 12 维或按公司标准)
- **自定义评委角色** (客户内部真专家的 persona)
- **数据不出企业** (用客户自己的 LLM API key / Azure OpenAI / 私有模型)
- **批量分析** (上传 Excel, 一次评 50 款游戏)
- **API 对外** (客户用 curl 直接调)

**报价思路**: $3k-10k/月 或一次性 $30k 定制费
**不要在 Pro 阶段就考虑, 可以等有第一个意向客户再启动**

---

## 4. 关键技术挑战 (逐项列清楚, 难点就暴露出来)

### 4.1 视频获取 (★★★★★ 最硬的骨头)

| 渠道 | 现状 | 难度 | 对策 |
| --- | --- | --- | --- |
| YouTube | yt-dlp 好用, 但有地区限制 / 反爬风险 | ★★★ | 用代理池 (IPRoyal / Bright Data $100-500/月), 或强制用户上传本地文件 |
| YouTube Shorts | 同上 | ★★★ | 同上 |
| Bilibili | 得登录 cookie 才能下高清, API 文档不全 | ★★★★ | `bilili` / `you-get` 工具, 或要求用户提供 Bilibili 账号 cookie |
| TikTok | 最难, 极强反爬 | ★★★★★ | 基本不做, 要求用户上传 |
| 抖音 | 同 TikTok | ★★★★★ | 不做 |
| 用户上传 | 稳 | ★ | 支持 mp4/mov, 限制大小 500MB |

**结论**: 
- MVP 阶段 **必须支持 YouTube + 用户上传** 两个口子
- **Bilibili 作为 v2 加功能**, 因为国内用户会要
- TikTok / 抖音明确不做, 让用户截图或自己录屏

**法务红线**:
- YouTube TOS 禁止自动下载, 但 yt-dlp 是灰区 (大量工具在用, 从没被告过小开发者)
- 只保留帧 (不保留原视频) 能大幅降低版权风险
- 报告里用的是 "评论性用途 (fair use)", 多数司法管辖区可辩护
- 但不能提供 "下载视频回传用户" 功能, 那是明确侵权

### 4.2 AI 成本 (★★★★★ 最实在的钱)

**Last Beacon MVP A 的实际消耗** (4/20 实测):
- Doubao Vision: 80 张帧 × 约 ¥0.01/张 = **¥0.8**
- LLM 评分 + summarize: 约 ¥2 (DeepSeek v3.2 或类似)
- Tavily: 约 ¥0.5 (3-5 次搜)
- **合计: 约 ¥3 / 单次评审 = $0.4**

**放大到 SaaS**:
- 免费用户 1/月: 吃 $0.4 损失
- Pro 用户 20/月: 成本 $8, 收费 $29 → 毛利 $21 (72%)
- 1000 Pro 用户: $21k/月 毛利

**降本策略**:
1. **帧数控制**: 从 80 帧降到 30 帧, 成本降 60% (但精度略损)
2. **缓存**: 同游戏 24h 内直接返回旧报告 (可降 30% 请求)
3. **模型分级**: 
   - 打标用便宜模型 (Doubao Vision / GLM-4V)
   - 评委评分用 Claude Sonnet 或 DeepSeek (不用 Opus)
   - 高付费用户才给 Opus 级深度
4. **批量 API**: OpenAI / Anthropic 都有 50% 折扣的 batch endpoint (异步 24h 内返回)

### 4.3 异步任务 (★★★★ 工程硬活)

**问题**: 一次评审 10-30 分钟, HTTP 肯定撑不住。

**架构**:
```
API: POST /reviews → 返回 job_id (<1 秒)
用户: 轮询 GET /reviews/:id → 拿进度
Worker: 后台跑 pipeline, 每步写进度到 Redis
完成: 发邮件 + Webhook + 前端推送 (SSE)
```

**失败处理**:
- 每步都 idempotent (重跑无副作用)
- 每步都有超时 (例如 ffmpeg 10 分钟超时自动 kill)
- 每个任务有预算上限 (跑到一半发现要花 $5 了就停)
- 失败后重试 3 次, 都失败发告警并退费

**推荐工具**:
- **Trigger.dev** (最省事, TypeScript 写任务, 有 UI 看进度) — 适合你这种产品
- **Celery + Redis** (Python 生态, 跟 skill 代码同语言) — 适合想完全自控
- **AWS Step Functions** (如果已经在 AWS) — 过度工程对小团队

### 4.4 多语言/本地化 (★★★ 中期要做)

**当前**:
- 所有评委 persona 是中文
- 报告是中文
- 提示词是中文

**如果要做国际版**:
- 评委 persona 要英文重写 (不能机翻, 会失真)
- 报告模板英文版
- 维度名字要翻 (D1 题材匹配度 → Theme Alignment, 可接受)
- 商店/视频字幕里的外语内容 → AI 翻译到用户母语 (新成本)

**建议**: 
- MVP 只做中文版
- 有第一个英文用户愿意付费 → 才做英文版
- 日语/韩语/东南亚语更后

### 4.5 维度定制 (★★★ 产品差异化关键)

**当前**: 7 维 D1-D7 是写死的 (review-board.md)。

**Web 化后的需求**:
- 立项评审 vs 外部观察 vs 投后复盘 vs 投资决策 → 每种场景维度不一样
- 腾讯的模板 ≠ 米哈游的模板 ≠ 你自己用的模板
- 用户可能想加自己的维度 (例如 "D8: 中国特供节日活动潜力")

**实现**:
- 系统提供 **4-5 套默认模板** (立项 / 上线观察 / 复盘 / 投资 / 发行)
- Pro 用户能 **自定义维度** (加 D8/D9/D10, 权重, 描述)
- Ent 用户能 **自定义评委 persona**

**这一点就是你问题里说的 "维度按模式可配置" — 现在 C 方案就是在为这个铺路**

### 4.6 合规/法务 (★★★★ 不能忽视)

| 风险 | 严重度 | 对策 |
| --- | --- | --- |
| YouTube TOS 不允许下载 | 中 | 只留帧, 不留原片; Terms 写清楚是 fair use 评论性用途 |
| 游戏公司说 "你在骂我产品" | 中 | 文案避免 "垃圾 / 骗钱", 用 "关注点 / 建议" 等中性词 |
| 用户传了盗版素材 | 低 | Terms 里转嫁责任给用户, 违规就封号 |
| 用户个人信息 (游戏账号) | 低 | Privacy Policy 说清楚存哪, 多久删 |
| 评审被用来当竞品情报打压对手 | 中 | 不接受定制的 "打击特定对手" 需求 |
| AI 生成内容免责 | 中 | 报告上写清楚 "本报告为 AI 辅助生成, 仅供参考, 不构成投资建议" |

**建议**: 找做过 SaaS 的律师 (国内月费 5k-1w) 起草一版 Terms + Privacy, 一次性费用 $2-5k 能覆盖大部分风险。

---

## 5. 渐进式落地路径 (6 个阶段)

> **千万不要跳阶段**。每一步都有独立验证价值, 每一步都能停下来。

### Phase 0: 当前 — Skill in Cursor (已完成)

- 状态: ✅ 完成 (Last Beacon MVP A 验证通过)
- 形态: 必须有 Cursor + Claude Opus 才能用
- 用户: 1 (你)
- 产出: 3 件套 + 反思文档

---

### Phase 1 ✅: Skill 独立化 = C 方案 (2026-04-21 完成, 实际 ~2.5 小时)

**为什么**: 
- 原 review 代码被塞在 `ppt-master` 里, 跟 "立项 PPT 评审" 耦合
- 要做外部游戏评审, 每次都在 ppt-master 里改代码, 混乱
- 想做 CLI / 网站, 得先有一个 "纯 review" 的干净代码库

**交付清单** (见 § 6.1 完成明细):

| 产出 | 位置 | 状态 |
| --- | --- | --- |
| 独立 skill 仓库 | `f:/Git/game-review/` | ✅ 与 ppt-master 平级 |
| README.md | `f:/Git/game-review/README.md` | ✅ |
| SKILL.md (AI 门面) | `f:/Git/game-review/skills/game-review/SKILL.md` | ✅ YAML frontmatter + 触发词 |
| review-board charter | `f:/Git/game-review/skills/game-review/references/review-board.md` | ✅ 7 维度稳定版 |
| 产品 roadmap (公开简版) | `f:/Git/game-review/docs/roadmap.md` | ✅ |
| `generate_review.py` 增强 | 加 `--mode {internal-ppt, external-game}` + `--with-visuals` + argparse | ✅ |
| `add_visual_sheet.py` 通用化 | 去硬编码 + 支持 `visual_catalog` / auto-scan / 动态反查 scene 文件 | ✅ |
| `build_summary.py` 镜像 | 未改动 | ✅ |
| `ppt-master` deprecation 指引 | `ppt-master/skills/ppt-master/scripts/review/DEPRECATED.md` + `review-board.md` 头部 mirror 提示 | ✅ |
| Last Beacon 端到端验证 | 4 件套 + 视觉索引 13 rows × 13 images | ✅ |

**验证数据**: Last Beacon 跑完产出 docx 52KB / xlsx 951KB / md 14KB / review.json 41KB, 视觉索引 sheet `15 rows × 5 cols + 13 embedded images`。✓

---

### Phase 2: CLI 打包 (0.5-1 天)

**为什么**:
- Skill 必须靠 agent 理解意图才跑; CLI 能让不懂 Claude 的同事直接 `game-review analyze <url>`
- 验证 "脱离 agent 能不能用" — 这是能不能变 Web 的前提
- 能接到公司内部工作流 (CI / GitHub Actions / 定时任务)

**做什么**:
- `pip install -e .` 安装
- `game-review store <url>` → 只做素材收集
- `game-review analyze <project-dir> [--mode external-game --with-visuals]` → 出报告
- `game-review summary <project-dir>...` → 跨项目汇总
- 环境变量管理 (`.env` 读 ARK/TAVILY key)

**验证**: 把 CLI 装到一台 **没有 Cursor** 的 Windows 机器上跑, 能产出 Last Beacon 报告。

---

### Phase 3: 单用户 Web MVP (3-5 天)

**为什么**:
- 第一次让 **不会用命令行的人** 能用上
- 验证产品假设 — 用户真的愿意填表单等 30 分钟吗

**做什么**:
- 前端: Next.js 单页 (一个表单 + 一个结果页)
- 后端: FastAPI 1 个 endpoint + 1 个 background task (Python threading 就行)
- 认证: 写一个密码 (不做账号系统, 就你+3 个朋友用)
- 存储: 本地盘 / 单个 Supabase DB
- 部署: 单台 VPS ($10/月) 或 Fly.io
- **不做**: 支付 / 多租户 / Rate limit / 邮件 / Stripe

**验证**: 你女朋友/你爸/一个不懂技术的制作人朋友能自己上网点按钮出报告。

---

### Phase 4: 多租户 SaaS (2-3 周)

**为什么**: 
- 开始收钱
- 验证 PMF (product-market fit)

**做什么**:
- 加 Clerk 账号体系
- 加 Celery + Redis 队列
- 加 Stripe 订阅
- 加 rate limit + cost guard
- 加邮件通知 + 报告分享链接
- 加后台 admin dashboard (你能监控所有任务)

**验证**: 发到 Product Hunt / 游戏行业群, 拿到 **付费** 第一单 (哪怕只有 $29)。

---

### Phase 5: 开放平台 / 企业版 (可选, 有需求再做)

- API 对外
- 企业私有化
- 白牌 (白标)
- 定制维度 / 评委 persona
- 批量分析

---

### 5.1 Phase 1 完成明细 (v2 新增, 2026-04-21)

#### 决策回顾

原计划 "0.5-1 天", 实际 ~2.5 小时 (pure coding + 验证, 不含文档写作)。

#### 目录结构

```
f:/Git/game-review/                          # 新独立 skill repo
├── README.md                                 # 4.1 KB, 仓库门面
├── docs/
│   └── roadmap.md                            # 3.4 KB, 公开版产品路线图
└── skills/
    └── game-review/
        ├── SKILL.md                          # 6.7 KB, AI agent 读的 skill 门面 (YAML frontmatter + 触发词)
        ├── references/
        │   └── review-board.md               # 8.7 KB, 评委会 charter (7 维度稳定版)
        └── scripts/
            └── review/
                ├── generate_review.py        # 23.9 KB, 主入口, argparse + --mode + --with-visuals
                ├── build_summary.py          # 8.6 KB, 跨项目汇总
                └── add_visual_sheet.py       # 14.7 KB, 通用化视觉索引生成器
```

#### 关键能力提升

| 能力 | 原版 (ppt-master / Last-Beacon 私有脚本) | 新版 (game-review skill) |
| --- | --- | --- |
| **调用接口** | `python generate_review.py <dir>` | `python generate_review.py <dir> --mode {...} --with-visuals` |
| **mode 语义** | 无 (单模式) | `internal-ppt` (默认) / `external-game` |
| **视觉索引** | Last Beacon 私有脚本, 硬编码 6 张 + 7 帧 | 通用化, 任意项目都能用 |
| **商店图发现** | 硬编码 `screenshot_01-06` | 优先 `visual_catalog.store`, fallback auto-scan `raw_assets/*/store/*/` (支持 googleplay/appstore/steam 等) |
| **视频帧发现** | 硬编码 `scene_1281/3396/5289/...` | 从 `video_evidence.key_scenes_human_read` 动态, 按 `scene_<id>` 自动反查任意子目录 |
| **JSON schema** | 6 字段 | +2 可选字段 (`video_evidence`, `visual_catalog.store`) |
| **与 ppt-master 关系** | 紧耦合 | 解耦, 后者加 DEPRECATED.md 指引 |

#### 验证数据 (Last Beacon 作为回归测试)

- **执行时间**: ~2.3 秒完成 3 件套 + 视觉索引
- **Word**: 52 KB (197 行)
- **Excel**: 951 KB (13 张嵌入图 + 4 sheets: Issues / Scores / 视觉索引 / Action_Items)
- **Subjective MD**: 14 KB
- **视觉索引 sheet**: 15 rows × 5 cols (含 1 行表头 + 1 行说明 + 13 行数据), 13 张缩略图全部嵌入成功

#### 发现的 Gap (往后的 TODO)

1. `ppt-master/scripts/game_assets/fetch_game_assets.py` 的 `_heuristic_label` bug (竖屏帧误判为 ui-menu), 阻塞 80 帧 AI 打标 — 已记录在 `Last-Beacon_review.json.video_evidence.skill_gaps_found`, 等 Phase 2 做 CLI 时回哺
2. `fetch_game_assets.py` 不接受 `--video-url` 手动指定 (硬编码 ytsearch) — 同上
3. `_heuristic_label` 只出 single label 无描述 — 同上
4. `--game` argparse 前缀匹配冲突 `--gameplay-only` — 同上

#### 兼容性承诺

E/H/I 内部项目继续用旧脚本 (`ppt-master/skills/ppt-master/scripts/review/*.py`), **短期不影响**。本季度内, 新项目推荐用新 skill; 长期旧脚本可能删除 (当所有 in-flight 项目都迁移完)。

---

## 6. 成本估算

### 6.1 开发投入

| 阶段 | 时间 | 你自己做 (有 Cursor) | 外包 (纯人工) |
| --- | --- | --- | --- |
| Phase 1 (C 方案) | 0.5-1 天 | 0 (今天就做) | ¥2-5k |
| Phase 2 (CLI) | 0.5-1 天 | 0 | ¥3-5k |
| Phase 3 (单用户 Web) | 3-5 天 | 0 (你主导 + Cursor 写代码) | ¥2-5w |
| Phase 4 (多租户 SaaS) | 2-3 周 | 0-2w (买 Clerk/Stripe/基础设施) | ¥10-30w |
| Phase 5 (企业版) | 按需 | - | 按需 |

### 6.2 运营成本 (Phase 3-4 阶段)

| 项 | 月成本 | 说明 |
| --- | --- | --- |
| Vercel Pro | $20 | 前端托管 |
| Fly.io / Render | $10-50 | 后端 + worker |
| Supabase Pro | $25 | DB + Auth |
| Cloudflare R2 | $5-20 | 视频帧/报告存储 |
| Clerk | $25 | 用户系统 (免费到 10k MAU) |
| Redis (Upstash) | $10 | 队列 |
| Sentry | $26 | 错误追踪 |
| 代理 (IPRoyal) | $100-500 | 视频下载, 可选 |
| 邮件 (Resend) | $0-20 | 通知 |
| **固定总计** | **$220-700** | - |

**AI API** (变动, 按量):
- 1 份报告平均 $0.4-1
- 100 份/月: $40-100
- 1000 份/月: $400-1000
- 10000 份/月: $4000-10000

**定价建议** (Phase 4):
- Free: 1 份/月 (给所有人体验)
- Pro $29/月: 20 份/月 (毛利 ~70%)
- Team $99/月: 100 份/月 (毛利 ~60%)
- Ent: $3k/年起, 私有化 / 自定义维度

**盈亏平衡**: **~30 个 Pro 用户** (约 $870 MRR) 能覆盖基础设施。

---

## 7. C 方案 (Phase 1) 跟这一切的关系

> 这是你今天最该关心的问题。

C 方案 = **Phase 1 = skill 独立化**, 它对未来每个阶段都是必经之路:

```
你现在 (Phase 0)          →   Skill 藏在 ppt-master 里
  ↓ 做 C 方案 (Phase 1)
独立 game-review skill    →   脱离 ppt-master, 代码干净
  ↓ Phase 2
CLI 可安装                 →   同事能在自己电脑跑
  ↓ Phase 3
单用户 Web                 →   非技术人能用
  ↓ Phase 4
多租户 SaaS                →   收钱了
```

**不做 C 方案就直接做 Web, 会怎样**:
- 你在 web 后端里还得 import ppt-master 的代码
- ppt-master 本来是 "评 PPT" 的, 跟 "评外部游戏" 的逻辑混在一起会越来越乱
- 别人接手代码, 根本搞不清楚哪部分是 review 哪部分是 PPT 生成
- 改一个维度得改 3 个文件

**做了 C 方案之后**:
- game-review skill 能独立跑, 独立测
- 后端 web 直接 `subprocess.run(["game-review", "analyze", ...])` 或 `from game_review import run_review()`
- ppt-master 保留 "生 PPT" 的本职工作, 不管评审
- 新加维度只改 1 个地方

**结论: C 方案是今天必须做的。**

---

## 8. 风险红线 (什么时候该停)

| 红线 | 处理 |
| --- | --- |
| AI API 月消耗超 **$500** 没客户 | 暂停 Phase 4, 回到 Phase 3 打磨 |
| Phase 3 做完 **3 个月没有人** 愿意付 $29 | 产品方向不对, 重新想 |
| Google 发正式律师函 (不是普通 TOS 提醒) | 立刻下架视频下载, 只做用户上传 |
| 上线 **3 个月内 NPS 低于 0** | 优先修产品, 不加功能 |
| 你一个人撑不住 (正职+副业打架) | 停在 Phase 3, 不冲 SaaS |

---

## 9. 附: 决策点清单 (让你今天拍)

这些问题你得回答一个大方向, 不需要太细:

1. **目标**: 这个网站是 **给自己/同事用的小工具** 还是 **要对外做 SaaS 收钱**?
   - 前者: Phase 3 就够, 别做 Phase 4
   - 后者: 规划要到 Phase 4-5

2. **时间投入**: 你能每周投 **5 小时 / 10 小时 / 20 小时** 做这个?
   - 5h: Phase 1-2 做完就停一阵
   - 10h: Phase 3 (4-6 周)
   - 20h: Phase 4 (3-4 个月)

3. **预算**: 每月愿意烧 **$100 / $500 / $2000** 养这个?
   - $100: Phase 3 玩玩
   - $500: Phase 4 启动
   - $2000: Phase 4 认真做

4. **客户**: 你**现在有没有** 3-5 个真愿意付钱试用的内测用户?
   - 有: 直接冲 Phase 4
   - 没: 停在 Phase 3, 先找到用户再说

5. **Bus factor**: 只有你一个人, 还是能拉 1 个前端同学 + 1 个后端同学?
   - 只有你: Phase 3 OK, Phase 4 会很累
   - 3 人小队: Phase 4 舒服很多

**我的建议 (给你参考)**: Phase 1-2 今天做 (总 1-1.5 天), Phase 3 周末做 (4-5 天), Phase 4 等至少 3 个外部真实用户问 "这能付费吗" 再启动。**不要一次冲到 Phase 4。**

---

## 10. 下一步 · 4 周 Action List (v2 拍板版)

基于 § 0.5 用户决策 (B/B/C/A), 把原"10. 下一步"具体化为可执行的 2-4 周 action list。

### Week 0 (已完成 ✅, 2026-04-21)

- [x] Phase 1 (C 方案): game-review skill 独立化
- [x] 更新 roadmap v2 (本文档)
- [x] 推送到 Git 各自 remote

### Week 1 · Phase 2 + 泛化验证 (5-10h) — "ABC 串行"

> 这个子路线来自 2026-04-21 session 末尾的推荐: **A (CLI 打包) + B (挑验证游戏) + C (Web MVP 蓝图)** 串行, 总工作量约 2 小时核心 + 5-8h 执行。

#### 1A: CLI 打包 (0.5-1 天, 核心 30-60 分钟)

**目标**: 脱离 AI agent, 一个命令就能跑评审。

**做什么**:
- [ ] 在 `f:/Git/game-review/` 根目录加 `pyproject.toml` + `src/` (或直接 `game_review/` python package) 
- [ ] 加 entry point: `[project.scripts] game-review = "game_review.cli:main"`
- [ ] 写薄的 `cli.py` (仅 argparse 子命令派发), 把 `scripts/review/*.py` 作为库函数调用
- [ ] 本地 `pip install -e .` 测试
- [ ] 3 个子命令:
  - `game-review analyze <project-dir> [--mode] [--with-visuals]` — 等同现在的 `generate_review.py`
  - `game-review summary <batch-dir>` — 等同 `build_summary.py`
  - `game-review init <name>` — **新功能**, 生成 review.json 骨架模板 (带占位符, 让 agent 填)

**验证**: 在一台没装 Cursor 的机器上能 `pip install game-review` + `game-review analyze ...` 跑通。

#### 1B: 挑 2-3 款验证游戏 + 跑泛化测试 (3-5h)

**目标**: 证明 skill 框架不只适用 SLG, 能通吃不同品类。

**候选清单** (选 2 款, 覆盖 Last Beacon 以外的品类):

| 候选 | 品类 | 为什么选 | 数据获取难度 |
| --- | --- | --- | --- |
| **Whiteout Survival** | SLG + 末日幸存 | Last Beacon 的直系对标, 验证 benchmark 准确度 | ⭐ (Google Play 直接有) |
| **Last War: Survival** | SLG + 射击 | 全球 SLG Top 3, 验证商业化维度 | ⭐ |
| **Frost Punk Mobile** | 剧情城建 | 剧情导向 ≠ SLG, 验证 D1 题材匹配维度 | ⭐⭐ (Steam 也能取) |
| **放置少女 / AFK 2** | 放置 RPG | 超休闲放置 ≠ 重度 SLG, 验证 D5 付费维度 | ⭐ |
| **崩坏: 星穹铁道** | 二次元回合 | 高付费赛道 ≠ SLG, 验证 D6 风险合规维度 | ⭐⭐ |

**测试清单** (每款):
- [ ] 用 ppt-master 的 `fetch_game_assets` 抓商店 + 视频 (沿用 Last Beacon 路径)
- [ ] agent 基于素材填 `review.json` (schema 见 game-review SKILL.md)
- [ ] `game-review analyze --mode external-game --with-visuals` 出 4 件套
- [ ] 人工检查: 结论是否荒谬 / 维度是否缺失 / visual_catalog 是否匹配

**通过条件**: 2 款都能 < 30 分钟产出 4 件套 + 评审结论不荒谬。
**不通过条件**: 任意 1 款挂了, Week 2 改 skill 而不是冲 Web。

#### 1C: Phase 3 Web MVP 蓝图 (0.5-1h)

**目标**: 给 Week 2-4 一份"照着做就行"的蓝图文档。

**产出**: `f:/Git/game-review/docs/webmvp_plan.md`, 包含:

- [ ] 技术栈最终选型 (Next.js 14 + Tailwind + shadcn/ui + FastAPI + SQLite)
- [ ] 页面 wireframe (表单页 + 结果页 + 历史页), 用 ASCII art 或 markdown 简图
- [ ] API 契约 (`POST /reviews` / `GET /reviews/:id` / `GET /reviews/:id/report.xlsx`)
- [ ] 数据模型 (`reviews` 表 + `jobs` 表 + `assets` 表)
- [ ] 部署策略 (Fly.io 单机 + 本地密码认证)
- [ ] 成本限制 (每任务 $2 上限)
- [ ] 本地跑起来的 docker-compose (方便以后同事协作)

### Week 2 · Phase 3 前端 (5-10h)

- [ ] Next.js 14 项目脚手架 (`f:/Git/game-review-web/` 作为新独立 repo)
- [ ] 表单页 (shadcn/ui Form 组件, 支持商店 URL + 视频 URL 多填 + 模式选择)
- [ ] 结果页 (展示 4 件套摘要 + 下载链接 + 视觉索引缩略图预览)
- [ ] 历史页 (列出以前的 review, 点击进结果页)
- [ ] Mock API 打通 (先写假数据, 不连后端)

### Week 3 · Phase 3 后端 + 本地 E2E (5-10h)

- [ ] FastAPI 单机后端 (`game-review-web/backend/`)
- [ ] 后台任务用 Python `threading` (第一版不做异步队列, 反正只 3-5 人用)
- [ ] SQLite 存 reviews / jobs
- [ ] 单密码认证 (cookie 保持)
- [ ] 用 Last Beacon 跑一次完整的 Web 流程自测

### Week 4 · 部署 + 隐藏版内测 (3-5h)

- [ ] Fly.io / Railway 部署 (选一个, 不折腾)
- [ ] 配置域名 (可选, 先用默认 `*.fly.dev` 也行)
- [ ] 把 URL 私下发给那 3-5 个问过的人, 附上 "隐藏版内测, 不分享" 的 note
- [ ] 收 2-3 人的反馈 (用什么记录? 建议开一个 `丁开心的游戏观察/internal-feedback.md`)

### Month 2+ · Phase 4 触发决策

按 § 0.5 里的 3 条件 gate, 满足才启动 Phase 4; 不满足继续自用或开源。

### 长期观察清单 (每月 review 一次)

- [ ] AI API 累计消耗 (如果 > $500/月 且无付费客户 → 降频 or 暂停)
- [ ] 内测用户实际跑的次数 (如果 3 个月没人跑第 2 次 → 产品方向不对)
- [ ] 合规事件 (任何 cease-and-desist 都触发紧急响应)

---

## 11. 待办 · 本文档维护

- [ ] **v3 更新时机**: Phase 2 完成后 (CLI 可 pip install + 2 款游戏验证通过)
- [ ] **v4 更新时机**: Phase 3 完成后 (Web 上线 + 3-5 人内测有反馈)
- [ ] **v5 更新时机**: Phase 4 启动决策做完 (启动/停止/改方向)

---

> 本文档随项目进展更新, 标注版本号。
> v1 (2026-04-20): Last Beacon MVP A 完成后的初稿, 10 章可行性。
> v2 (2026-04-21): 用户拍板方向 + Phase 1 完成 + 本周 action 具体化。
