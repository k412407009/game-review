"""game-review-api · Phase 3 Web MVP 后端

把 game-review CLI 编排成 Web 服务:
  1. POST /jobs             提交评审任务 (game_id + 可选 store_url/video_url + 可选上传 raw_assets.zip / review.json)
  2. GET  /jobs/{job_id}    查询进度 + 下载链接
  3. GET  /jobs/{job_id}/download  下载产物 zip

业务流水线:
  [stage 1: fetch]      抓素材 (Phase 3 stub: 如上传了就用, 没上传就 mock)
  [stage 2: score]      AI 生成 review.json (Phase 3 stub: 固定中性评分 + TODO 接真实 LLM)
  [stage 3: generate]   调 game-review CLI 生成三件套
  [stage 4: package]    zip 产物, 返回下载链接
"""

__version__ = "0.1.0"
