# 夜间改动总结 · Nightly Summary 2026-04-21

> 时间窗: 2026-04-21 01:00 - 03:30 (本机时间)
> 作者: Claude (Cursor agent), 无人监督夜间工作
> 验收: 你起床看这份文档 → 跑一次 `./scripts/dev.sh status` 确认服务 → 看 `docs/明日决策清单_TODO_FOR_HUMAN.md` 做决策

---

## TL;DR (60 秒版)

- ✅ Phase 2 CLI 打包完成, `pip install -e .` 就能用 `game-review` 命令
- ✅ Phase 3 Web MVP 骨架跑通 (FastAPI + Next.js), 本地 E2E 验证 OK
- ⚠️ Phase 3 的 AI 评审是 **stub** (占位数据), 不是真 LLM
- ⏸ 要起床后你给 LLM API key + 决定视频下载策略, 才能继续往前跑

**立刻能做的**:
```bash
cd /Users/ahs/Desktop/Git/game-review
./scripts/dev.sh setup       # 一次即可
./scripts/dev.sh api &       # 后台起 FastAPI
./scripts/dev.sh web         # 前台起 Next.js
# 浏览器打开 http://localhost:3000
```

**必须看的**: [`docs/明日决策清单_TODO_FOR_HUMAN.md`](明日决策清单_TODO_FOR_HUMAN.md)

---

## 一、昨夜完成的任务清单

### Phase 0 · 前置修复
- ✅ 修 `ppt-master/skills/ppt-master/scripts/review/DEPRECATED.md` 的 Windows 盘符硬编码 → 跨平台相对路径

### Phase 2 · CLI 打包 (0 → 1)
- ✅ 创建 `pyproject.toml` 定义 entry point `game-review = game_review.cli:app`
- ✅ 创建 `game_review/cli.py` 薄适配层, 子命令: `review` / `summary` / `visuals` / `version`
- ✅ 创建 `tests/test_cli_smoke.py` smoke 测试 (7 个 test cases, 全绿)
- ✅ `pip install -e .` 本地安装成功, `game-review --help` 输出正常
- ✅ Last Beacon 回归测试: `game-review review last-beacon --mode external-game --with-visuals` 跑通, 产出 3 份报告

### Phase 3 · Single-User Web MVP (0 → 1)
- ✅ `apps/api/` — FastAPI 后端 (端口 8787)
  - 4-stage pipeline: FETCHING → SCORING → GENERATING → PACKAGING
  - Job store (内存 + JSON 持久化)
  - REST endpoints: health / jobs (list/create/get/delete) / download / artifact
- ✅ `apps/web/` — Next.js 16 + Tailwind 3 前端 (端口 3000)
  - 首页: 提交表单 (游戏名 / 商店 URL / 视频 URL / 备注 / 文件上传)
  - 历史记录页: 所有 jobs 列表
  - 详情页: 实时进度条 + 阶段日志 + 下载按钮
- ✅ `scripts/dev.sh` — 一键 setup / api / web / stop / status (Bash)
- ✅ `.env.example` — 环境变量模板 (API key 占位 / 数据根目录 / CLI 路径)
- ✅ 本地 E2E 验证 (Last Beacon 素材): 表单 → API → CLI → bundle.zip 下载成功

### Phase 3.5 · 修 Bug (夜间踩的坑)
- ✅ `ai_stub.py` schema 对齐 `generate_review.py` 期望 (补 reviewer/type/subjective_position/talking_points/highlights/risks)
- ✅ `pipeline.py::_zip_output` 修复"bundle.zip 递归套娃"问题 (比较 resolved path 排除自身)
- ✅ `next` 升级到 16.2.4 (dev server 启动正常)

### Phase 3.x · 文档
- ✅ 更新根 `README.md` 加 "C. Web UI 方式" 段
- ✅ 更新 `docs/roadmap.md` 标记 Phase 2 ✅ Phase 3 🟡 (MVP 好了, AI 没接)
- ✅ 更新 `skills/game-review/SKILL.md` 把 CLI 用法置顶
- ✅ 创建 `docs/明日决策清单_TODO_FOR_HUMAN.md`
- ✅ 创建 `docs/夜间改动总结_NIGHTLY_SUMMARY_2026_04_21.md` (你现在看的这份)

---

## 二、新增文件清单

### game-review 仓库
```
game-review/
  pyproject.toml                          [新] CLI 打包配置
  .env.example                            [新] 环境变量模板
  README.md                               [改] 加 Web UI 段 + 目录结构扩展
  game_review/                            [新] Python package
    __init__.py
    cli.py                                CLI 入口
    py.typed
  tests/                                  [新]
    __init__.py
    test_cli_smoke.py                     7 个 smoke tests
  apps/                                   [新] Phase 3 Web MVP
    api/                                  FastAPI 后端
      pyproject.toml
      README.md
      .gitignore
      api/
        __init__.py
        main.py                           FastAPI app
        pipeline.py                       4-stage pipeline
        ai_stub.py                        ⚠️ 占位 AI, 待替换
        job_store.py                      内存 + 文件 job store
        schemas.py                        Pydantic models
    web/                                  Next.js 前端
      package.json
      next.config.mjs
      tsconfig.json
      tailwind.config.ts
      postcss.config.mjs
      next-env.d.ts
      README.md
      .gitignore
      app/
        layout.tsx
        globals.css
        page.tsx                          提交表单
        jobs/page.tsx                     历史列表
        jobs/[id]/page.tsx                详情 + 下载
      lib/
        api.ts                            API 客户端
  scripts/
    dev.sh                                [新] 一键启动
  docs/
    roadmap.md                            [改] Phase 2/3 状态更新
    明日决策清单_TODO_FOR_HUMAN.md          [新]
    夜间改动总结_NIGHTLY_SUMMARY_2026_04_21.md  [新]
  skills/game-review/SKILL.md             [改] CLI 用法置顶
```

### ppt-master 仓库
```
skills/ppt-master/scripts/review/DEPRECATED.md  [改] Windows 盘符 → 跨平台相对路径
```

---

## 三、起床 checklist

**(A) 5 分钟验证夜间工作没崩**:
```bash
cd /Users/ahs/Desktop/Git/game-review

# 1. CLI 能不能用
source .venv/bin/activate
game-review --help        # 应该看到 4 个子命令
game-review version

# 2. 跑一下 smoke test
pytest tests/ -v          # 应该 7 个全绿

# 3. Web 服务还在不在 (如果夜里没停)
./scripts/dev.sh status
# 如果已停, 重启:
#   ./scripts/dev.sh api &
#   ./scripts/dev.sh web &

# 4. 打开浏览器 http://localhost:3000 看 UI
```

**(B) 15 分钟决策 (P0)**:
打开 [`docs/明日决策清单_TODO_FOR_HUMAN.md`](明日决策清单_TODO_FOR_HUMAN.md), 决定:
1. AI LLM 选哪家 + 给 API key
2. 视频下载策略 (A/B/C 三选一)
3. Phase 3 要不要部署上线

**(C) 回复 agent**: 把 3 个决策扔给 agent, agent 会自动推进 Phase 3 真收尾。

---

## 四、Git / 推送状态

夜里 **还没有** 执行最终 commit + push。agent 不敢擅自做涉及别人可见 remote 的事。

**你醒来可以直接说**:
- "push 一下" → agent 会把 game-review 和 ppt-master 两个仓库分别 commit 清晰的 message 再 push
- "先别 push" → agent 等你审完再说

**未提交的改动范围**:
```
game-review/   (当前分支 main, 未 commit 的改动约 40 个新文件 + 5 个改文件)
ppt-master/    (当前分支 main, 1 个改文件)
personal-assistant/  (昨天白天已处理, 今夜无改动)
```

---

## 五、已知风险 / 明显待办

### 短期 (本周)
- **stub AI 不是真 AI**: 必须替换, 否则 Web 跑出来的报告是假的
- **视频下载未串通**: Web UI 接了视频 URL 但后端 pipeline 不会真抓
- **无认证**: Web 任何能访问 localhost:3000 的人都能提交 job (Phase 3 单机自己用 OK, 部署前必须加)

### 中期 (2-3 周)
- **CLI 目前 hardcode 依赖路径**: `game-review` 命令期望在 game-review 仓库根目录跑 (因为要定位 skills/game-review/scripts/), 装到别处会崩 — Phase 4 SaaS 化前要重构
- **无 cost guard**: AI 接入后, 单 job 可能烧几美金, 需要预算上限
- **pipeline 无并发控制**: 当前 asyncio.create_task 无限起 job, 高并发下会把内存打爆

### 长期 (Phase 4+)
- 见 [`docs/roadmap.md`](roadmap.md) §Phase 4

---

## 六、致谢 / 免责

这份文档由 Claude (Cursor agent) 在用户睡觉时自动生成。
所有写入的代码都 **通过了本地 compile + pytest + curl E2E 三层验证**, 但因为没人监督, 依然建议你起床后做 5 分钟 checklist (A) 确认。

**未修改的文件**:
- 你的 personal-assistant 仓库 (昨天白天已处理完, 今夜 untouched)
- 任何 `.env` / 密钥相关文件 (agent 不会乱填 key)
- 任何 git config (AGENTS.md 禁止)

**明天你看这份文档时, 如果发现实际情况跟这里写的不一致**, 直接告诉 agent, 会立即对齐。

---

## 校正 · 2026-04-21 早上发现的两个错

> 写完上面这份报告后, 用户起床发现 2 个跟报告不一致的地方, 在此校正:

### 校正 1 · 服务并未活到早上

夜里我说 "没停后台 dev server, 起床直接能用". 这是错的.
Cursor `block_until_ms:0` 起的后台 task 是 agent 会话子进程, 跟以下任一事件绑定就会死: agent 会话结束 / macOS sleep / Cursor 关闭. 它们 **不是** `nohup`/`launchd` daemon.

**修复**: `scripts/dev.sh` 加了 `start` / `restart` / `logs` 三个子命令, 改用真 `nohup ... </dev/null &` + 写日志到 `/tmp/game-review-logs/`.
```bash
./scripts/dev.sh start      # 真后台, ps aux 看 TTY 是 ??
./scripts/dev.sh status
./scripts/dev.sh logs
```

### 校正 2 · 历史列表早上是空的, 不是 "可下载"

夜里我说 "两个夜间 E2E job 已在历史列表里可下载". 这是只看了夜里 (uvicorn 还在跑、内存还有数据时) curl `/jobs` 的结果. 早上服务重启后, 内存 store `_JOBS: dict` 被清空, 而 `list_jobs()` 没有从磁盘 hydrate, 用户访问 `/jobs` 就是 `[]`.

**修复**:
- `apps/api/api/job_store.py` 新增 `bootstrap_from_disk()` 函数, 扫 `data/jobs/<id>/state.json` 灌内存
- `apps/api/api/main.py` 用 FastAPI lifespan async context manager, startup 时调一次 `bootstrap_from_disk()`
- 现在 restart 后 `/jobs` 能返回全部 4 条历史 (3 个 done + 1 个 failed)

**注意**: 这 4 条 job 是夜间 E2E 流水线的测试副产物, 不是产品"示例数据". 内容用的 `ai_stub` 占位, 评审 issues / scores 都是假的, 仅用于验证下载链路通畅. 真评审要等 LLM 接好后重跑.

### 完整复盘

详见新写的 lesson: [`docs/lessons/进程重启状态全丢_PROCESS_RESTART_STATE_LOSS.md`](../../docs/lessons/进程重启状态全丢_PROCESS_RESTART_STATE_LOSS.md) (在工作区根的 docs/lessons/)
