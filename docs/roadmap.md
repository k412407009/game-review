# game-review Roadmap

> 从 **skill → CLI → Web SaaS** 的渐进落地路径。
> 这里是 **公开版概要** (面向 Git 仓库访问者); 私有版的完整成本/时间/竞品分析在作者的个人项目目录。

## 当前状态: v0.1 (2026-04-21)

- ✅ 从 `ppt-master` 独立, 7 维度 charter 稳定
- ✅ 两种模式 (`--mode internal-ppt` / `--mode external-game`)
- ✅ `--with-visuals` 自动嵌入商店截图 + 视频关键帧缩略图到 Excel
- ✅ Last Beacon: Survival 作为外部游戏评审首个案例验证通过

## 发展阶段

### Phase 1 ✅ Skill 独立化 (已完成, 2026-04-21)

从 ppt-master 剥离, 成为可单独引用的 skill。

### Phase 2 ⏳ CLI 打包 (计划中, 0.5-1 天)

**目标**: 脱离 AI agent 也能用。

**交付**:
- `pyproject.toml` 定义 entry point
- `pip install -e .` 安装后可直接 `game-review analyze <dir>`
- 环境变量 / `.env` 管理
- `game-review init <project-name>` 快速生成 review.json 骨架

### Phase 3 ⏳ Single-User Web MVP (规划中, 3-5 天)

**目标**: 让不懂命令行的制作人 / 研究员能用。

**技术栈**:
- Next.js 14 (App Router) + Tailwind + shadcn/ui
- FastAPI (单进程) + 本地文件存储
- 单密码认证 (不做账号系统)

**支持输入**:
- Google Play / App Store / Steam 链接
- YouTube / Bilibili 视频链接 (最多 3 个)
- 参考文章链接 (最多 5 个)
- 重点维度 / 对标产品 (选填)

**支持输出**:
- 网页报告 (可分享)
- 下载 Word / Excel / Markdown 包

### Phase 4 ⏳ Multi-Tenant SaaS (远期, 2-3 周)

**目标**: 可付费商业化。

**加入**:
- Clerk 账号体系
- Celery + Redis 任务队列
- Stripe 订阅 (Free / Pro / Team)
- Rate limit + cost guard (单任务预算上限)
- S3 存储视频帧 / 报告
- 邮件通知 + Webhook + 后台 admin dashboard

**定价**:
- Free: 1 份/月
- Pro $29/月: 20 份/月
- Team $99/月: 100 份/月

### Phase 5 ⏳ 企业版 / 开放平台 (按需)

- SSO / 私有化部署
- 自定义维度 / 自定义评委 persona
- API 对外
- 白牌 (白标)

## 关键技术挑战

| 挑战 | 影响 | 对策 |
| --- | --- | --- |
| YouTube 视频下载 (反爬 / 地区限制) | Phase 3+ 最大 blocker | 代理池 + 用户上传 fallback |
| AI API 月度成本控制 | Phase 4 毛利决定因素 | 帧数控制 + 结果缓存 + 模型分级 |
| 异步任务 (10-30 分钟) | Phase 3+ | Trigger.dev / Celery + 进度反馈 |
| 多语言本地化 | 国际化前阻塞 | 先做中文, 验证 PMF 再扩 |
| 法务合规 (视频 TOS / 版权) | Phase 4+ 合规底线 | 只留帧, fair use 免责, 拒绝敏感题材 |

## 成本估算

| 阶段 | 自己做时间投入 | 基础设施月成本 | AI API 月成本 (量产后) |
| --- | --- | --- | --- |
| Phase 1 ✅ | 半天 | $0 | ~$1/次 (自用) |
| Phase 2 | 半天 | $0 | ~$1/次 |
| Phase 3 | 3-5 天 | $20-50 | ~$1/次 × 月用量 |
| Phase 4 | 2-3 周 | $220-700 | $0.4-1/任务 × 任务量 |

## 风险红线

- 月度 AI 消耗 > $500 且无付费客户 → 暂停 Phase 4, 回 Phase 3 打磨
- Phase 3 上线 3 个月无人付 $29 → 产品方向不对, 复盘
- 收到游戏公司正式律师函 → 下架视频下载, 改纯用户上传

## 决策心法

**先别冲 SaaS**。优先做 Phase 1-2, 累积 5-10 款游戏的评审样本, 验证框架的泛化能力。有 **3-5 个愿意付费的潜在用户** 再启动 Phase 4。
