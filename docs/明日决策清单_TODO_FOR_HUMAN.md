# 明日决策清单 · TODO FOR HUMAN

> 这份是 **只有你能拍板** 的事, 按优先级排序。
> 昨夜 (2026-04-21) agent 已把 Phase 2 CLI 打包 + Phase 3 Web MVP 骨架跑通, 但下面这些事情不是 agent 能替你决定的。

---

## P0 · 必须当天决定 (否则 Phase 3 真正收尾会 block)

### 1. AI 评审接哪家 LLM?

**现状**: `apps/api/api/ai_stub.py` 生成的是 **占位 review.json**, 真实评审根本没跑。Web 表单点"开始评审"拿到的产物里, issues/scores 全是假数据。

**你要选一个**:

| 候选 | 优点 | 缺点 | 预估成本 |
| --- | --- | --- | --- |
| **Claude (Anthropic) Sonnet 4.5** | 5 评委 × 7 维度这种结构化评审最稳, 中文流畅 | 没做 prompt engineering 前 token 消耗偏大 | ~$0.5-1.5 / 份 |
| **GPT-4o / GPT-5** | 工具链成熟, JSON mode 稳 | 中文细腻度弱于 Claude | ~$0.3-1.0 / 份 |
| **DeepSeek V3** | 便宜 10x, 中文好 | 结构化 JSON 偶尔漏字段, 要加 retry | ~$0.05-0.15 / 份 |
| **Gemini 2.5 Pro** | 便宜 + 长上下文放原素材 (截图/帧) 有优势 | 评审质量次一档 | ~$0.15-0.4 / 份 |

**推荐**: MVP 阶段用 **Claude Sonnet + DeepSeek 双路由** — Claude 做主评审, DeepSeek 做 fallback / 轻量任务 (如 summary)。
参考 lesson: `docs/lessons/LLM额度耗尽降级_LLM_QUOTA_FALLBACK_ROUTER.md` 的 ModelRouter 模式。

**你的决定**:
- [ ] 选定 LLM 家
- [ ] 提供 API key (写进 `.env`, 不要 commit)
- [ ] 是否要用 ModelRouter 多路由降级

---

### 2. 视频下载策略

**现状**: `game-review` 本仓库 **没有** 视频下载能力。Last Beacon 之所以能跑通, 是因为素材是 agent 帮你预先抓好放到 `last-beacon/raw_assets/`。

**Web 用户填了 YouTube / Bilibili 链接后, 要怎么做?**

| 方案 | 优点 | 缺点 |
| --- | --- | --- |
| **A. 复用 ppt-master 的 fetch_game_assets** | 已有代码, 能直接抓 Steam / YouTube | 要把 ppt-master 的子集搬到 game-review, 或让 game-review 依赖 ppt-master package |
| **B. 只接受用户上传 raw_assets.zip** | 法务干净, 代码简单 | 用户体验差, 普通人不会搞 |
| **C. 用 yt-dlp + 代理池** | 自动化程度高 | 反爬会被封, 法务风险, 运维累 |

**推荐**: **Phase 3 阶段走 A, Phase 4 SaaS 化时加 B 作为 fallback, 永远不走 C**。

**你的决定**:
- [ ] 是否把 `fetch_game_assets.py` 从 ppt-master 搬进 game-review (我建议 git submodule 或单独发 pypi 包)
- [ ] 还是只靠用户上传 zip

---

### 3. Phase 3 要不要上线到公网?

**现状**: 只能 `localhost:3000` 本机跑。

**选项**:

| 部署选项 | 成本 | 适用 |
| --- | --- | --- |
| **不部署, 纯本地** | $0 | 只自己用, 不分享 |
| **Run Platform (run.ingarena.net)** | 已有, $0 额外 | 内部分享, 有 SKILL `run-platform-deploy` |
| **Railway / Render / Fly.io** | $5-20/月 | 对外 demo |
| **自己 VPS + Docker Compose** | $5-10/月 | 完全掌控 |

**推荐**: **先 Run Platform** 内部分享, 等有第一个外部用户再挪 Railway。

**你的决定**:
- [ ] 要不要部署
- [ ] 部署到哪
- [ ] 域名要什么 (`game-review.ingarena.net`? `review.你的域.com`?)

---

## P1 · 本周内决定 (否则 Phase 4 SaaS 化 block)

### 4. 候选评审游戏名单

MVP 阶段需要 **5-10 款** 已上线游戏作为评审样本, 验证框架泛化能力。

**类型建议** (至少覆盖):
- [ ] 1 款 Steam 大作 (已有 Last Beacon)
- [ ] 1 款 Steam 小作 (独立游戏)
- [ ] 1 款 Mobile F2P
- [ ] 1 款 Mobile 买断
- [ ] 1 款 海外独立
- [ ] 1 款 国产独立
- [ ] 1 款 失败案例 (Steam 差评 / 下架) — 用于验证框架能不能识别出失败原因

**你的决定**: 列出你想评审的 5-10 款游戏名单。

---

### 5. 真付费用户是谁?

Phase 4 SaaS 化需要先验证 **付费意愿**。

**定位**:
- A. 独立游戏制作人 — 愿意为"第三方视角评审"付 $29/月
- B. 发行商 BD / 评估 — 愿意为"批量评审竞品"付 $99/月
- C. 游戏投资机构 — 愿意为"投前尽调"付 $500+/月

**你的决定**:
- [ ] 主打哪一类
- [ ] 有没有 3-5 个候选 beta 用户
- [ ] 定价怎么定 (roadmap 里的 $29/$99 要不要改)

---

## P2 · 两周内决定 (Phase 4 Kickoff 前)

### 6. 法务 / 版权红线

- [ ] 视频帧留存是否合规 (fair use 判定)
- [ ] 成人游戏 / 敏感题材怎么过滤
- [ ] 评审报告输出后, 责任归属 (免责条款怎么写)

### 7. 技术栈锁定

- [ ] Phase 4 继续 FastAPI + Next.js, 还是换 Rust (Axum) / Go (Gin)
- [ ] 任务队列选 Celery+Redis / Trigger.dev / Inngest / AWS SQS
- [ ] 存储: S3 / Cloudflare R2 / 自建 minio
- [ ] 账号体系: Clerk / Auth0 / 自研

### 8. 商业变现节奏

- [ ] 要不要先做 Pro Hunt / 独立游戏社区推广
- [ ] 要不要做中文 demo video 放 B 站 / 抖音
- [ ] 要不要做英文落地页先收 waitlist

---

## 你不需要决定, agent 会处理的事

这部分是 agent 夜里已经做完或后续会自动推进的:

- ✅ `pyproject.toml` 打包 + CLI entry point
- ✅ FastAPI pipeline orchestration
- ✅ Next.js 前端 MVP
- ✅ 本地 E2E 跑通 (Last Beacon 素材)
- ✅ 中文 docs 命名规则合规
- ✅ 跨平台 (macOS/Windows) 路径修正
- ⏳ 把 stub 替换成真 LLM (等你给 API key 后自动推进)
- ⏳ 把 ppt-master 的 fetch_game_assets 集成 (等你 P0 #2 决策后自动推进)

---

## 如何使用这份清单

1. 早上起来第一件事: 看 **P0** 的 3 个选项, 每个二选一
2. 选完后在对应 checkbox 打钩, 把决定回复给 agent (或直接编辑本文件然后 commit)
3. Agent 会根据你的决定自动推进 Phase 3 收尾 + Phase 4 kickoff

> **注意**: P0 里任一项不决定, 今天都做不了实质进展。其他可以慢慢来。
