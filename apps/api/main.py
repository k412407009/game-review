"""RUN / PaaS 入口.

Run 平台的运行时探测会在 `apps/api/` 根目录寻找 `main.py`,
并执行 `python3 main.py`。这里显式转发到 `api.main:app`。
"""

from __future__ import annotations

import os

import uvicorn


if __name__ == "__main__":
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
        reload=False,
    )
