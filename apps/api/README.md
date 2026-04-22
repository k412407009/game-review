# apps/api · game-review Web API (Phase 3 MVP)

FastAPI 后端, 把 `game-review` CLI 编排成 HTTP 流水线。

## 启动

```bash
# 在 repo 根目录
cd /path/to/game-review

# 复用根 venv (game-review CLI 已经装好了)
source .venv/bin/activate

# 装 API 依赖
cd apps/api
pip install -e .

# 启动 dev server (默认 :8787)
uvicorn api.main:app --reload --port 8787

# 看 API docs
open http://localhost:8787/docs
```

## 健康检查

```bash
curl http://localhost:8787/health
# {"status":"ok","version":"0.1.0","data_root":".../data/jobs"}
```

## 核心接口

| Method | Path | 说明 |
| --- | --- | --- |
| POST | `/jobs` | 提交评审任务 (multipart/form-data) |
| GET  | `/jobs` | 列表 (最多 50 条, 按创建时间倒序) |
| GET  | `/jobs/{id}` | 查询进度 + 产物列表 |
| GET  | `/jobs/{id}/download` | 下载 bundle.zip |
| GET  | `/jobs/{id}/artifact/{name}` | 下载单个产物 (docx/xlsx/md) |
| DELETE | `/jobs/{id}` | 删除 job + 磁盘数据 |

## 提交任务示例

```bash
# A. 只填元数据 → API 默认调用 Compass 生成 review.json
curl -X POST http://localhost:8787/jobs \
  -F "game_id=last-beacon" \
  -F "game_name=Last Beacon: Survival" \
  -F "mode=external-game" \
  -F "with_visuals=true" \
  -F "store_url=https://play.google.com/store/apps/details?id=com.hnhs.endlesssea.gp" \
  -F "video_url=https://youtube.com/watch?v=..."

# B. 上传用户准备好的 review.json (跳过 AI 评审, 直接走 CLI)
curl -X POST http://localhost:8787/jobs \
  -F "game_id=last-beacon" \
  -F "game_name=Last Beacon: Survival" \
  -F "mode=external-game" \
  -F "with_visuals=true" \
  -F "review_json=@/path/to/review.json" \
  -F "raw_assets_zip=@/path/to/raw_assets.zip"
```

## 流水线阶段

```
QUEUED → FETCHING → SCORING → GENERATING → PACKAGING → DONE
                                                       ↘ FAILED (任何一步出错)
```

1. **FETCHING**: 解压 `raw_assets.zip` 到 `workdir/raw_assets/` (如果上传)
2. **SCORING**: 用 Compass 生成 review.json, 或直接复制用户上传的
3. **GENERATING**: 执行 `game-review review <workdir> --mode ... [--with-visuals]`
4. **PACKAGING**: 把 `output/*.{docx,xlsx,md}` 打包成 zip

> 本地如果同级存在 `../game-asset-collector/scripts/fetch_game_assets.py`,
> API 的 FETCH 阶段会优先调用这份共享采集器做商店抓取 / 视频抽帧 / labels / descriptions 生成，
> 这样网站链路和 Skill 链路使用的是同一套采集逻辑。
> 找不到共享采集器时，会先退回 `../ppt-master/.../fetch_game_assets.py` wrapper；
> 两者都不可用时，才回退到 `api/rich_context.py` 自带的轻量 collector。

## 存储布局

```
apps/api/data/jobs/<job_id>/
  request.json          用户提交的表单
  progress.json         最新进度
  state.json            完整状态 (重启恢复用)
  input/
    review.json         (可选) 用户上传
    raw_assets.zip      (可选) 用户上传
  workdir/
    review/<game>_review.json   ← 喂给 CLI
    raw_assets/...               ← CLI 找素材用
  output/
    <game>_review.docx
    <game>_review.xlsx
    <game>_subjective_responses.md
    <game>_review_bundle.zip    ← /download 返回这个
```

## 环境变量

| Var | 默认 | 说明 |
| --- | --- | --- |
| `GAME_REVIEW_DATA_ROOT` | `apps/api/data` | job 数据根目录 |
| `GAME_REVIEW_CLI` | `python -m game_review.cli` | CLI 调用方式, 可指向其他 venv |
| `COMPASS_API_KEY` | - | Compass 鉴权 key。未配置时自动回退到本地 stub |
| `COMPASS_MODEL` | `compass-max` | 默认评审模型 |
| `COMPASS_BASE_URL` | `https://compass.llm.shopee.io/compass-api/v1` | Compass OpenAI 兼容入口 |
| `COMPASS_TIMEOUT_SECONDS` | `120` | 单次评审 HTTP 超时 |

## ⚠️ Phase 3 已知限制

1. **评审质量依赖输入资料** — 只给游戏名时, Compass 只能做保守判断；补充 `store_url` / `video_url` / `notes` 会明显更好
2. **Compass 失败会回退到 stub** — 流水线不会断, 但产物会明确标记为占位评审
3. **没有用户系统** — 单用户 / 无鉴权, 跑在本机
4. **没有持久队列** — 服务重启运行中的 job 不会自动恢复 (但历史记录从磁盘能恢复)
5. **自动抓取仍有限** — 当前已支持 `reference_url` / `notes` 中的 `mp.weixin` 链接抓正文，且会自动抓取 Google Play / App Store 商店文案和 YouTube 关键帧；其他站点仍需逐步扩展

见 `docs/roadmap.md` 了解 Phase 4 计划。
