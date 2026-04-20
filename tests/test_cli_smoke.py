"""CLI smoke tests · 只测 CLI 层的启动/参数解析, 不跑真实评审业务

业务回归测试需要 raw_assets/ 数据, 放到 personal-assistant 下的 e2e 测试里, 不在 repo 内。
"""

from __future__ import annotations

import subprocess
import sys

import pytest


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "game_review.cli", *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_module_runnable_as_script():
    r = _run("--help")
    assert r.returncode == 0, r.stderr
    assert "game-review" in r.stdout
    assert "review" in r.stdout
    assert "summary" in r.stdout
    assert "visuals" in r.stdout


def test_version_subcommand():
    r = _run("version")
    assert r.returncode == 0, r.stderr
    assert "game-review" in r.stdout


def test_version_flag():
    r = _run("--version")
    assert r.returncode == 0, r.stderr
    assert "game-review" in r.stdout


@pytest.mark.parametrize("sub", ["review", "summary", "visuals"])
def test_subcommand_help(sub: str):
    r = _run(sub, "--help")
    assert r.returncode == 0, r.stderr
    assert "usage:" in r.stdout.lower()


def test_review_requires_project_dir():
    r = _run("review")
    assert r.returncode != 0
    assert "required" in r.stderr.lower() or "project_dir" in r.stderr.lower()


def test_review_invalid_mode_rejected():
    r = _run("review", "/tmp/nonexistent", "--mode", "invalid-mode")
    assert r.returncode != 0
    assert "invalid choice" in r.stderr.lower() or "mode" in r.stderr.lower()


def test_review_nonexistent_dir_fails_gracefully():
    r = _run("review", "/tmp/game-review-does-not-exist-xyz")
    assert r.returncode != 0


def test_cli_module_importable():
    from game_review import cli

    assert callable(cli.app)
    assert hasattr(cli, "_build_parser")


def test_package_version_exposed():
    import game_review

    assert hasattr(game_review, "__version__")
    assert isinstance(game_review.__version__, str)
