# apps/web · game-review Web UI (Phase 3 MVP)

Next.js 15 + Tailwind 3 + React 19 前端, 本地默认跑在 `localhost:3000`; 生产环境默认对接 `https://api.run.ingarena.net`, 本地开发可用 `NEXT_PUBLIC_API_URL` 覆盖。

## 启动

```bash
cd apps/web
npm install           # 首次 (约 1-2 分钟, 下载 Next.js/React/Tailwind)
npm run dev           # 开 http://localhost:3000
```

**前提**: 同时启动后端, 见 `../api/README.md`. 如果不启动, 前端会显示 API 错误提示.

```bash
# 另开一个终端
cd apps/api
source ../../.venv/bin/activate
uvicorn api.main:app --reload --port 8787
```

## 页面

| 路径 | 作用 |
| --- | --- |
| `/` | 提交评审表单 |
| `/jobs` | 历史记录列表 |
| `/jobs/[id]` | 单个 job 进度页 (轮询 1.5s) + 下载入口 |

## 环境变量

| Var | 默认 | 说明 |
| --- | --- | --- |
| `NEXT_PUBLIC_API_URL` | `https://api.run.ingarena.net` | 后端 API 地址, 本地开发时建议改成 `http://localhost:8787` |

如果后端跑在其他端口/机器, 建 `apps/web/.env.local`:

```bash
NEXT_PUBLIC_API_URL=http://your-api-host:8787
```

## Production build

```bash
npm run build
npm run start         # :3000
```

## Phase 3 设计约束

- **单用户, 无鉴权** — 跑在本机或内网, 不面向公网
- **无 DB** — 数据放在后端磁盘 `apps/api/data/jobs/`, 重启不丢历史但丢运行中任务
- **Tailwind 3.4** — Tailwind 4 稍有不兼容 Next.js 15, Phase 3 先用 v3 稳

Phase 4 多租户时会加: NextAuth / 数据库 / Redis 队列 / 文件 CDN, 见 `docs/roadmap.md`.

## 不引入完整 shadcn/ui 的原因

`shadcn/ui init` 会引入 lucide-react / Radix UI / class-variance-authority 等 8+ 依赖,
Phase 3 MVP 页面只有 3 个 (表单 + 列表 + 进度), 用 Tailwind 手写更轻.
Phase 4 多租户 / 复杂交互时再引入 shadcn.
