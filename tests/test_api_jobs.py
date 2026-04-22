from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from api import main as api_main
from api import job_store


def _make_client(tmp_path: Path, monkeypatch) -> TestClient:
    jobs_root = tmp_path / "jobs"
    jobs_root.mkdir(parents=True, exist_ok=True)

    job_store._JOBS.clear()
    monkeypatch.setattr(job_store, "JOBS_ROOT", jobs_root)
    monkeypatch.setattr(api_main, "JOBS_ROOT", jobs_root)

    async def fake_run_pipeline(_: str) -> None:
        return None

    monkeypatch.setattr(api_main, "run_pipeline", fake_run_pipeline)
    return TestClient(api_main.app)


def test_create_job_accepts_empty_notes(tmp_path: Path, monkeypatch) -> None:
    client = _make_client(tmp_path, monkeypatch)

    response = client.post(
        "/jobs",
        data={
            "game_id": "empty-notes",
            "game_name": "Empty Notes",
            "mode": "external-game",
            "with_visuals": "true",
            "notes": "",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["request"]["notes"] is None
    assert body["progress"]["stage"] == "queued"


def test_create_job_accepts_whitespace_notes_as_empty(tmp_path: Path, monkeypatch) -> None:
    client = _make_client(tmp_path, monkeypatch)

    response = client.post(
        "/jobs",
        data={
            "game_id": "blank-notes",
            "game_name": "Blank Notes",
            "mode": "external-game",
            "with_visuals": "true",
            "notes": "   ",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["request"]["notes"] is None


def test_create_job_accepts_short_notes_and_reference_url(tmp_path: Path, monkeypatch) -> None:
    client = _make_client(tmp_path, monkeypatch)

    response = client.post(
        "/jobs",
        data={
            "game_id": "short-notes",
            "game_name": "Short Notes",
            "mode": "external-game",
            "with_visuals": "false",
            "reference_url": "https://mp.weixin.qq.com/s/demo",
            "notes": "a",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["request"]["notes"] == "a"
    assert body["request"]["reference_url"] == "https://mp.weixin.qq.com/s/demo"


def test_create_job_reuses_same_client_request_id(tmp_path: Path, monkeypatch) -> None:
    client = _make_client(tmp_path, monkeypatch)
    payload = {
        "game_id": "idempotent-job",
        "game_name": "Idempotent Job",
        "client_request_id": "req-123",
        "mode": "external-game",
        "with_visuals": "false",
    }

    first = client.post("/jobs", data=payload)
    assert first.status_code == 201
    first_body = first.json()

    second = client.post("/jobs", data=payload)
    assert second.status_code == 200
    second_body = second.json()
    assert second_body["job_id"] == first_body["job_id"]

    recovered = client.get("/jobs/by-client-request/req-123")
    assert recovered.status_code == 200
    assert recovered.json()["job_id"] == first_body["job_id"]


def test_create_job_rejects_overlong_notes(tmp_path: Path, monkeypatch) -> None:
    client = _make_client(tmp_path, monkeypatch)

    response = client.post(
        "/jobs",
        data={
            "game_id": "too-long-notes",
            "game_name": "Too Long Notes",
            "mode": "external-game",
            "with_visuals": "false",
            "notes": "x" * 20001,
        },
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail
    assert "at most 20000 characters" in detail[0]["msg"]
