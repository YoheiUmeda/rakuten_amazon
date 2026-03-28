# tests/test_run_review.py
"""
run_review wrapper のテスト。
openai / OPENAI_API_KEY 不要。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT   = Path(__file__).resolve().parents[1]
VENV_PYTHON = REPO_ROOT / "venv" / "Scripts" / "python.exe"


def _py() -> str:
    return str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable


def _args(**kwargs) -> argparse.Namespace:
    """テスト用 Namespace を生成するヘルパー。"""
    defaults = dict(
        task="テスト", staged=False, files=[], test_cmd="",
        run_tests=False, related_code=[], open_questions=[],
        constraints=[], dry_run=False,
    )
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


# ──────────────────────────────────────────────────────────────────────────
# subprocess CLI テスト
# ──────────────────────────────────────────────────────────────────────────

class TestRunReviewCLI:

    def test_dry_run_exits_zero(self):
        """--dry-run が exit 0 で終わること。"""
        r = subprocess.run(
            [_py(), "-m", "tools.ai_orchestrator.run_review",
             "--task", "テスト", "--staged", "--dry-run"],
            capture_output=True, text=True, encoding="utf-8", cwd=REPO_ROOT,
        )
        assert r.returncode == 0, f"stderr: {r.stderr}"


# ──────────────────────────────────────────────────────────────────────────
# fail-open 経路テスト（monkeypatch）
# ──────────────────────────────────────────────────────────────────────────

class TestFailOpen:

    def test_generate_nonzero_exit_is_failopen(self, monkeypatch):
        """generate が returncode=1 → run_review は sys.exit(0)（fail-open）。"""
        from tools.ai_orchestrator import run_review
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: subprocess.CompletedProcess([], returncode=1),
        )
        with pytest.raises(SystemExit) as exc:
            run_review.run(_args())
        assert exc.value.code == 0

    def test_orchestrator_nonzero_exit_is_failopen(self, monkeypatch):
        """orchestrator が returncode=1 → run_review は sys.exit(0)（fail-open）。"""
        from tools.ai_orchestrator import run_review
        call_count: dict[str, int] = {"n": 0}

        def fake_run(*a, **kw):
            call_count["n"] += 1
            # 1回目（generate）成功、2回目（orchestrator）失敗
            return subprocess.CompletedProcess([], returncode=0 if call_count["n"] == 1 else 1)

        monkeypatch.setattr(subprocess, "run", fake_run)
        with pytest.raises(SystemExit) as exc:
            run_review.run(_args())
        assert exc.value.code == 0

    def test_dry_run_skips_orchestrator(self, monkeypatch):
        """--dry-run のとき orchestrator が呼ばれないこと。"""
        from tools.ai_orchestrator import run_review
        call_count: dict[str, int] = {"n": 0}

        def fake_run(*a, **kw):
            call_count["n"] += 1
            return subprocess.CompletedProcess([], returncode=0)

        monkeypatch.setattr(subprocess, "run", fake_run)
        run_review.run(_args(dry_run=True))
        assert call_count["n"] == 1  # generate のみ、orchestrator は呼ばれない
