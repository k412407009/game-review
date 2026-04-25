"""One-off: 把 Last-Beacon_review.json 里的 SS01-SS06 代号换成中文短语。

跑一次就够, 完成后可删。理由: 评委代号对非技术用户不友好, 全局换成
"封面图 / 基地图 / 采集图 / 防御战图 / 联盟战图 / 抽卡图" 更直观。
"""
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except Exception:
    pass

FILES = [
    Path(r"F:\Git\丁亮的个人助手\丁开心的游戏观察\external-game-reviews\Last-Beacon-Survival\review\Last-Beacon_review.json"),
    Path(r"F:\Git\丁亮的个人助手\丁开心的游戏观察\external-game-reviews\Last-Beacon-Survival\external_game_brief.md"),
]

REPLACEMENTS = [
    (r"SS01-SS06", "6 张商店图"),
    (r"SS01-06", "6 张商店图"),
    (r"SS02-SS06", "玩法图(基地/采集/战斗/抽卡)"),
    (r"SS02-06", "玩法图(基地/采集/战斗/抽卡)"),
    (r"SS01", "封面图"),
    (r"SS02", "基地图"),
    (r"SS03", "采集图"),
    (r"SS04", "防御战图"),
    (r"SS05", "联盟战图"),
    (r"SS06", "抽卡图"),
]


def main() -> int:
    for p in FILES:
        if not p.exists():
            print(f"  SKIP (missing): {p}")
            continue
        s = p.read_text(encoding="utf-8")
        total = 0
        for pat, rep in REPLACEMENTS:
            count = len(re.findall(pat, s))
            if count:
                s = re.sub(pat, rep, s)
                total += count
                print(f"  {p.name}: {pat} -> {rep}  x{count}")
        p.write_text(s, encoding="utf-8")
        leftover = re.findall(r"SS\d{2}", s)
        left_str = ", ".join(sorted(set(leftover))) if leftover else "(none)"
        print(f"  [{p.name}] total {total} replacements, leftover SSxx: {left_str}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
