"""game-review · 5 评委 × 7 维度评审 CLI

Entry point: `game-review` (see pyproject.toml [project.scripts])

Package 内只放薄 CLI 适配层; 真实评审逻辑在 skill 脚本里
(`skills/game-review/scripts/review/*.py`), 通过 sys.path 注入调用。

这样做是为了:
  1. skill 目录继续对 Cursor/Claude 等 AI agent 可见 (/skills/<name>/ 约定)
  2. pip 安装后, 命令行用户也能直接 `game-review review ...`
  3. 未来 Phase 3 Web 层只需 import 这里的 cli.app, 无需再读 skill 脚本路径
"""

__version__ = "0.1.0"
