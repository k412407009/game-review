from __future__ import annotations

import json
from pathlib import Path

from api import rich_context


def test_fetch_asset_context_bundle_composes_notes_and_review_fields(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(rich_context, "_collect_with_ppt_master_fetcher", lambda **_: None)

    def fake_store(**_: object) -> rich_context.StoreEvidence:
        return rich_context.StoreEvidence(
            source="googleplay",
            page_url="https://play.google.com/store/apps/details?id=com.demo.game",
            title="Demo Game",
            developer="Demo Studio",
            description="A very long store description",
            rating="4.4",
            installs="100000+",
            genre="Strategy",
            release_info="2026-04-01",
            icon_path="raw_assets/demo/store/googleplay/icon.png",
            screenshot_paths=[
                "raw_assets/demo/store/googleplay/screenshot_01.jpg",
                "raw_assets/demo/store/googleplay/screenshot_02.jpg",
            ],
            video_url=None,
            raw_metadata={"source": "googleplay"},
        )

    def fake_video(**_: object) -> rich_context.VideoEvidence:
        return rich_context.VideoEvidence(
            source_url="https://www.youtube.com/watch?v=demo",
            resolved_url="https://www.youtube.com/watch?v=demo",
            title="Demo Gameplay",
            uploader="Uploader",
            duration_seconds=185,
            description="Gameplay overview",
            frame_paths=[
                "raw_assets/demo/gameplay/frames/demo_video/scene_0001.jpg",
                "raw_assets/demo/gameplay/frames/demo_video/scene_0003.jpg",
            ],
            frame_interval_seconds=12,
            raw_metadata={"id": "demo"},
        )

    monkeypatch.setattr(rich_context, "_collect_store_evidence", fake_store)
    monkeypatch.setattr(rich_context, "_collect_video_evidence", fake_video)

    bundle = rich_context.fetch_asset_context_bundle(
        game_id="demo",
        game_name="Demo Game",
        store_url="https://play.google.com/store/apps/details?id=com.demo.game",
        video_url="https://www.youtube.com/watch?v=demo",
        notes="重点看 D1 / D2 / D7",
        output_dir=tmp_path,
    )

    assert bundle.store is not None
    assert bundle.video is not None
    assert bundle.enriched_notes is not None
    assert "[自动抓取商店页证据]" in bundle.enriched_notes
    assert "[自动抽取视频证据]" in bundle.enriched_notes
    assert "D1 题材匹配度" in bundle.enriched_notes
    assert "D2 核心循环" in bundle.enriched_notes

    visual_store = bundle.review_fields["visual_catalog"]["store"]
    assert len(visual_store) == 2
    assert visual_store[0]["path"] == "raw_assets/demo/store/googleplay/screenshot_01.jpg"

    scenes = bundle.review_fields["video_evidence"]["frame_analysis"]["key_scenes_human_read"]
    assert len(scenes) == 2
    assert scenes[0]["frame"].startswith("scene_0001")
    assert scenes[0]["dims_affected"] == ["D2", "D7"]

    payload = json.loads((tmp_path / "context" / "asset_context.json").read_text(encoding="utf-8"))
    assert payload["store"]["title"] == "Demo Game"
    assert payload["video"]["title"] == "Demo Gameplay"


def test_fetch_asset_context_bundle_collects_warnings_without_failing(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(rich_context, "_collect_with_ppt_master_fetcher", lambda **_: None)

    def broken_store(**_: object):
        raise RuntimeError("store failed")

    monkeypatch.setattr(rich_context, "_collect_store_evidence", broken_store)

    bundle = rich_context.fetch_asset_context_bundle(
        game_id="demo",
        game_name="Demo Game",
        store_url="https://play.google.com/store/apps/details?id=com.demo.game",
        video_url=None,
        notes=None,
        output_dir=tmp_path,
    )

    assert bundle.store is None
    assert bundle.video is None
    assert bundle.warnings
    assert "商店页自动抓取失败" in bundle.warnings[0]


def test_select_appstore_candidate_rejects_fuzzy_match() -> None:
    results = [
        {"trackName": "Last Fortress: Underground", "bundleId": "com.more.lastfortress.appstore"},
        {"trackName": "Last Island of Survival", "bundleId": "com.herogame.ios.lastdayrules"},
    ]

    app, reason = rich_context._select_appstore_candidate("Last Beacon Survival", results)

    assert app is None
    assert "too weak" in reason or "ambiguous" in reason


def test_select_appstore_candidate_accepts_clear_match() -> None:
    results = [
        {"trackName": "Last Fortress: Underground", "bundleId": "com.more.lastfortress.appstore"},
        {"trackName": "Last Island of Survival", "bundleId": "com.herogame.ios.lastdayrules"},
    ]

    app, reason = rich_context._select_appstore_candidate("Last Fortress Underground", results)

    assert app is not None
    assert app["trackName"] == "Last Fortress: Underground"
    assert "matched by title" in reason


def test_fetch_asset_context_bundle_prefers_ppt_master_bridge(
    tmp_path: Path, monkeypatch
) -> None:
    store = rich_context.StoreEvidence(
        source="googleplay",
        page_url="https://play.google.com/store/apps/details?id=com.demo.game",
        title="Demo Game",
        developer="Demo Studio",
        description="Store description",
        rating="4.6",
        installs="100000+",
        genre="Strategy",
        release_info="2026-04-01",
        icon_path="raw_assets/demo/store/googleplay/icon.png",
        screenshot_paths=["raw_assets/demo/store/googleplay/screenshot_01.jpg"],
        video_url=None,
        raw_metadata={"source": "googleplay", "descriptions": {"raw_assets/demo/store/googleplay/screenshot_01.jpg": "商店主图"}},
    )
    video = rich_context.VideoEvidence(
        source_url="https://www.youtube.com/watch?v=demo",
        resolved_url="https://www.youtube.com/watch?v=demo",
        title="Demo Gameplay",
        uploader="Uploader",
        duration_seconds=120,
        description="Gameplay description",
        frame_paths=["raw_assets/demo/gameplay/frames/demo_video/scene_0001.jpg"],
        frame_interval_seconds=5,
        raw_metadata={"scene_descriptions": {"scene_0001": "主城经营界面"}},
    )

    def fake_bridge(**_: object):
        return store, video, ["bridge ok"]

    def fail_store(**_: object):
        raise AssertionError("legacy store collector should not run")

    def fail_video(**_: object):
        raise AssertionError("legacy video collector should not run")

    monkeypatch.setattr(rich_context, "_collect_with_ppt_master_fetcher", fake_bridge)
    monkeypatch.setattr(rich_context, "_collect_store_evidence", fail_store)
    monkeypatch.setattr(rich_context, "_collect_video_evidence", fail_video)

    bundle = rich_context.fetch_asset_context_bundle(
        game_id="demo",
        game_name="Demo Game",
        store_url="https://play.google.com/store/apps/details?id=com.demo.game",
        video_url="https://www.youtube.com/watch?v=demo",
        notes=None,
        output_dir=tmp_path,
    )

    assert bundle.warnings == ["bridge ok"]
    assert bundle.store is not None
    assert bundle.video is not None
    scenes = bundle.review_fields["video_evidence"]["frame_analysis"]["key_scenes_human_read"]
    assert scenes[0]["content"] == "主城经营界面"
    assert "商店主图" in bundle.enriched_notes
