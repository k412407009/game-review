"""One-off Doubao Vision labeler for Last Beacon: Survival gameplay frames.

Why this exists:
  ppt-master/scripts/game_assets/fetch_game_assets.py has _heuristic_label
  that short-circuits every portrait frame (ratio < 0.7) to "ui-menu", which
  skips AI entirely for vertical-recorded mobile gameplay videos. Rather than
  patch the shared skill, we run this ad-hoc script once per external game.

What it does:
  * Walks <game_dir>/gameplay/frames/**/scene_*.jpg
  * For each frame: calls Doubao Vision (ARK) asking for a single label
    (12 categories) AND a 30-char Chinese description
  * Writes/merges <game_dir>/gameplay/labels.json (label map)
  * Writes/merges <game_dir>/gameplay/descriptions.json (desc map, our extra)

  Skips frames already present in BOTH files. Delete either file to force relabel.

TODO (skill layer, tracked in MVP_A_reflection.md):
  * Fix _heuristic_label to not mis-fire on portrait gameplay frames
  * Add description field to the shared label_frames output
"""
from __future__ import annotations

import base64
import io
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

# ---- config ---------------------------------------------------------------
GAME_DIR = Path(
    r"F:\Git\丁亮的个人助手\丁开心的游戏观察\external-game-reviews"
    r"\Last-Beacon-Survival\raw_assets\Last-Beacon-Survival"
)
GAME_NAME = "Last Beacon: Survival"
GAME_CTX = "一款 SLG + 海上生存主题手游, 核心玩法包含基地建造、抽卡英雄、小队 PVE、联盟战"
MODEL = "doubao-seed-1-6-vision-250815"
CATEGORIES = [
    "ui-menu", "battle", "shop-gacha", "main-city",
    "cutscene", "loading", "character", "map-world",
    "tutorial", "social", "ad-creative", "other",
]
ENV_PATH = Path(r"F:\Git\ppt-master\.env")
MAX_PX = 320
DETAIL = "low"
MAX_TOKENS = 120
SLEEP_BETWEEN = 0.25


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def resize_b64(img_path: Path, max_px: int = MAX_PX) -> str:
    from PIL import Image
    img = Image.open(img_path)
    img.thumbnail((max_px, max_px), Image.LANCZOS)
    if img.mode != "RGB":
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=70)
    return base64.b64encode(buf.getvalue()).decode()


def call_ark(b64: str, prompt: str, ark_key: str) -> tuple[str, int]:
    body = json.dumps({
        "model": MODEL,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url",
                 "image_url": {"url": f"data:image/jpeg;base64,{b64}",
                               "detail": DETAIL}},
                {"type": "text", "text": prompt},
            ],
        }],
        "max_tokens": MAX_TOKENS,
    }).encode()
    req = urllib.request.Request(
        "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
        data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {ark_key}"},
    )
    resp = urllib.request.urlopen(req, timeout=45)
    result = json.loads(resp.read().decode())
    content = result["choices"][0]["message"]["content"].strip()
    tokens = int(result.get("usage", {}).get("total_tokens", 0))
    return content, tokens


def parse_json_out(raw: str) -> tuple[str, str]:
    s = raw.strip()
    for fence in ("```json", "```JSON", "```"):
        s = s.replace(fence, "")
    s = s.strip().strip("`").strip()
    try:
        data = json.loads(s)
        label = str(data.get("label", "other")).strip().lower()
        desc = str(data.get("desc", "")).strip()
    except Exception:
        lo = s.lower()
        label = next((c for c in CATEGORIES if c in lo), "other")
        desc = s[:60]
    if label not in CATEGORIES:
        label = "other"
    return label, desc


def main() -> int:
    load_env(ENV_PATH)
    ark_key = os.environ.get("ARK_API_KEY", "").strip()
    if not ark_key:
        print("ERROR: ARK_API_KEY not set (checked env + .env)")
        return 1

    frames_dir = GAME_DIR / "gameplay" / "frames"
    if not frames_dir.exists():
        print(f"ERROR: no frames dir at {frames_dir}")
        return 1

    labels_path = GAME_DIR / "gameplay" / "labels.json"
    desc_path = GAME_DIR / "gameplay" / "descriptions.json"

    labels = {}
    descs = {}
    if labels_path.exists():
        try:
            labels = json.loads(labels_path.read_text(encoding="utf-8"))
        except Exception:
            labels = {}
    if desc_path.exists():
        try:
            descs = json.loads(desc_path.read_text(encoding="utf-8"))
        except Exception:
            descs = {}

    cats_str = ", ".join(CATEGORIES)
    prompt = (
        f"你在看一张{GAME_NAME}({GAME_CTX})的手机游戏截图。"
        f"严格只回答 JSON (不要 markdown 代码块), 格式: "
        f'{{"label":"<xxx>","desc":"<中文一句话, 不超过30字, 描述画面关键元素>"}}. '
        f"label 只能从以下 12 个中选一个: {cats_str}. "
        f"desc 要具体指出画面里的玩法阶段、功能或场景, 例如 '主城建造界面显示灯塔和10栋建筑' / "
        f"'抽卡池限免倒计时界面' / 'UP主片头logo' / '竖屏对话剧情框'."
    )

    frames = sorted(frames_dir.rglob("scene_*.jpg"))
    print(f"Found {len(frames)} frames under {frames_dir}")
    total_tokens = 0
    skipped = 0
    done = 0
    errors = 0
    errored: list[str] = []

    for i, img_path in enumerate(frames, 1):
        rel = img_path.relative_to(GAME_DIR).as_posix()
        if rel in labels and rel in descs and descs[rel] and not descs[rel].startswith("ERROR"):
            skipped += 1
            continue
        try:
            b64 = resize_b64(img_path)
            out, tokens = call_ark(b64, prompt, ark_key)
            total_tokens += tokens
            label, desc = parse_json_out(out)
            labels[rel] = label
            descs[rel] = desc
            print(f"[{i:>3}/{len(frames)}] {img_path.name:<32} -> {label:<14} | {desc}")
            done += 1
        except Exception as e:
            msg = str(e)[:80]
            print(f"[{i:>3}/{len(frames)}] {img_path.name:<32} ERROR: {msg}")
            if rel not in labels:
                labels[rel] = "other"
            descs[rel] = f"ERROR: {msg}"
            errored.append(rel)
            errors += 1
        time.sleep(SLEEP_BETWEEN)

    labels_path.write_text(
        json.dumps(labels, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    desc_path.write_text(
        json.dumps(descs, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    print(f"\nDone.  labeled={done}  skipped={skipped}  errors={errors}  total_tokens={total_tokens}")
    print(f"  labels.json       -> {labels_path}  ({len(labels)} entries)")
    print(f"  descriptions.json -> {desc_path}  ({len(descs)} entries)")

    by_tag: dict[str, int] = {}
    for v in labels.values():
        by_tag[v] = by_tag.get(v, 0) + 1
    print(f"  distribution: {dict(sorted(by_tag.items(), key=lambda x: -x[1]))}")
    if errored:
        print(f"  errored frames: {errored}")
    return 0 if errors == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
