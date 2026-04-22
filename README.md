# game-review

> 独立的 **"游戏评审委员会"** skill, 从 [game-ppt-master](https://github.com/k412407009/game-ppt-master) 剥离 (2026-04-21)。
>
> 以 5 位评委 (制作人 / 战略-题材 / 战略-玩法 / 运营-LTV / 运营-投放) × 7 维度 (题材 / 核心循环 / 时间节点 / 阶段过渡 / 商业化 / 风险合规 / 美术) 的结构, 把游戏评审变成可复现的结构化产出 (Word + Excel + Markdown).

## 在三仓架构里的位置

完整闭环推荐使用 3 个同级仓库：

- `game-ppt-master`
- `game-asset-collector`
- `game-review`

角色分工：

- `game-ppt-master`：主入口、PPT 工作流
- `game-asset-collector`：共享素材抓取
- `game-review`：结构化评审输出

总入口说明见 `../game-ppt-master/docs/三仓协同架构_THREE_REPO_STACK.md`
（兼容旧本地目录 `../ppt-master/docs/三仓协同架构_THREE_REPO_STACK.md`）。

## 为什么拆出来

- **game-ppt-master 的本职是 "生成 PPT"**, review 是它的收尾步骤, 耦合进主 skill 后, 外部游戏评审 (不生成 PPT 的场景) 变得难用
- 本 skill 支持 **两种输入源** (立项 PPT / 外部游戏), 未来扩展到 CLI / Web 服务更干净
- Web/API 侧的素材抓取现在**优先复用同级 `game-asset-collector` 的共享 `fetch_game_assets.py` 逻辑**，保证本地网站链路与 Skill 链路的抓取 / 抽帧 / 标注规则一致；找不到共享模块时，再回退到 `game-ppt-master` / `ppt-master` wrapper，最后才回退到自身内置 collector
- 详见 `docs/roadmap.md`

## 快速开始

### A. CLI 方式 (推荐, 2026-04-21 起可用)

```bash
# 1. clone & 进入目录
git clone https://github.com/k412407009/game-review.git
cd game-review

# 2. 建 venv (Python 3.10+) 并 editable 安装
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -e .

# 3. 准备 review.json (schema 见 skills/game-review/references/review-board.md §VI)
#    放到 <your_project>/review/<your_project>_review.json

# 4. 内部 PPT 评审 (默认)
game-review review <your_project>

# 4'. 外部游戏评审 (+ 视觉索引 Sheet)
game-review review <your_project> --mode external-game --with-visuals

# 4''. 正式生成前先体检项目目录
game-review doctor <your_project>

# 其他子命令
game-review summary <projects_root>           # 跨项目汇总
game-review visuals <your_project>            # 只追加视觉索引到已有 xlsx
game-review version                           # 版本
game-review --help                            # 完整用法
```

### B. 直接跑脚本 (不装包也行, 适合临时/cursor-skill 场景)

```bash
# 只装依赖
pip install python-docx openpyxl Pillow

# 运行脚本
python skills/game-review/scripts/review/generate_review.py <your_project>
python skills/game-review/scripts/review/generate_review.py <your_project> \
    --mode external-game --with-visuals
```

### C. Web UI 方式 (Phase 3 MVP, 2026-04-21 起可用)

单用户本地 Web 界面, 填表单 → 自动跑 pipeline → 下载产物 zip。

```bash
# 一键装 + 起 (需先 clone 本仓库)
./scripts/dev.sh setup       # 装 .venv + node_modules
./scripts/dev.sh api         # 终端 1: FastAPI → http://localhost:8787
./scripts/dev.sh web         # 终端 2: Next.js → http://localhost:3000
```

然后浏览器打开 http://localhost:3000, 填游戏名/商店 URL/视频 URL, 点"开始评审",
Pipeline 自动跑: 解压素材 / 自动抓商店页与关键帧 → Compass AI 评审 → CLI 生成报告 → 打包下载.

详见 [`apps/api/README.md`](apps/api/README.md) 和 [`apps/web/README.md`](apps/web/README.md).

---

产出 (三种方式一致):
- `<project>/review/<project>_review.docx` — 完整评审报告
- `<project>/review/<project>_review.xlsx` — Issues / Scores / (视觉索引) / Action_Items
- `<project>/review/<project>_subjective_responses.md` — 主观问题最优解

## external-game 的 `raw_assets` 约定

如果你希望 **以后还能字节级 / 视觉级复现** 同一份外部游戏评审, `raw_assets/` 不能只留
`metadata.json` 或最终 `xlsx`。最少要保留这几类原始证据:

- `<project>/raw_assets/<game>/store/...` — 商店截图原图
- `<project>/raw_assets/<game>/gameplay/frames/...` — 抽帧原图
- `<project>/raw_assets/<game>/gameplay/labels.json` — 场景标签
- `<project>/raw_assets/<game>/gameplay/descriptions.json` — 中文画面描述
- `<project>/raw_assets/<game>/metadata.json` — 抓取批次元数据

如果这些图源被删掉, `game-review --with-visuals` 仍能复现 **文字报告**, 但 Excel 的
"视觉索引" 会退化成 `(图源缺失)` 占位或只剩部分条目。

## 两种模式

| 模式 | 典型场景 | 输入 | 推荐 flag |
| --- | --- | --- | --- |
| `internal-ppt` (默认) | 内部立项评审, 已经做完 PPT | 自己写的 review.json | 无 |
| `external-game` | 外部上线游戏 / 竞品分析 / 投资决策 | `game-asset-collector` 的 `fetch_game_assets` 产出 + 自己写的 review.json | `--with-visuals` |

## 先跑 `doctor`

如果是第一次接手项目，建议先跑：

```bash
game-review doctor <project_dir>
```

它会检查：

- `review/` 目录是否存在
- `*_review.json` 是否存在且可解析
- `raw_assets/` 是否齐全
- `visual_catalog.store` / `video_evidence` 是否为空
- 已有 `docx/xlsx/md` 产物数量

## 目录结构

```
game-review/
  README.md                         你正在看的这个
  pyproject.toml                    CLI 打包配置 (Phase 2 — 2026-04-21)
  .env.example                      环境变量模板 (API key / 数据根目录 etc.)
  scripts/
    dev.sh                          本地一键启动 (setup / api / web / stop / status)
  game_review/                      Python package (CLI 适配层)
    __init__.py
    cli.py                          game-review CLI 入口 (subcommands: review/summary/visuals/version)
  tests/
    test_cli_smoke.py               CLI smoke tests (--help / 参数校验 / 版本)
  apps/                             Phase 3 Web MVP (2026-04-21)
    api/                            FastAPI 后端 (:8787) · pipeline orchestration
      api/main.py                   FastAPI app (jobs / download / artifact)
      api/pipeline.py               4-stage pipeline (fetch / score / generate / package)
      api/ai_stub.py                AI 评审 provider (默认 Compass; 失败回退 stub)
      api/job_store.py              内存 + 文件持久化 job store
      api/schemas.py                Pydantic 合约
    web/                            Next.js 15 + Tailwind 3 前端 (:3000)
      app/page.tsx                  提交表单
      app/jobs/page.tsx             历史记录
      app/jobs/[id]/page.tsx        进度页 + 下载
      lib/api.ts                    API 客户端
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

`game_review/cli.py` 是薄适配层, 把 CLI flag 透传给 `skills/game-review/scripts/review/*.py` 的脚本入口。
保持 skill 脚本作为"单一真实来源", CLI / Web / Agent 都只读它, 不复制。

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
  game-ppt-master (Step 1-7 生成 PPT)
    → game-ppt-master (Step 8 评委讨论, 填 review.json)
    → game-review (本 skill, 生成三件套)

[场景 B] 外部游戏评审:
  fetch_game_assets (收集商店/视频/买量素材)
    → agent 填 review.json (含 video_evidence 和 visual_catalog)
    → game-review --mode external-game --with-visuals (生成四件套)
```

## 文档

- [`docs/roadmap.md`](docs/roadmap.md) — 从 skill → CLI → Web SaaS 的渐进路径 + 成本/时间估算
- [`docs/赛道改造指南_TRACK_ADAPTATION_GUIDE.md`](docs/赛道改造指南_TRACK_ADAPTATION_GUIDE.md) — 哪些文件定义了评委、维度、权重、视觉标签，以及切换赛道时该改哪里
- [`skills/game-review/SKILL.md`](skills/game-review/SKILL.md) — AI agent 读的 skill 门面
- [`skills/game-review/references/review-board.md`](skills/game-review/references/review-board.md) — 评审委员会 charter (完整定义)

## License

MIT (本 skill 及其 scripts). 外部素材收集工具 (`game-asset-collector` / `game-ppt-master` wrapper / `ppt-master` legacy wrapper) 产出的视频帧 / 截图的版权归原游戏发行商所有, 本 skill 只生产 **评论性分析报告**, 建议遵循所在司法管辖区的 "合理使用 / fair use" 边界。
