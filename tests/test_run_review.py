# tests/test_run_review.py
"""
run_review wrapper の最小 dry-run テスト。
openai / OPENAI_API_KEY 不要。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT   = Path(__file__).resolve().parents[1]
VENV_PYTHON = REPO_ROOT / "venv" / "Scripts" / "python.exe"


def _py() -> str:
    return str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable


class TestRunReviewDryRun:

    def test_dry_run_exits_zero(self):
        """--dry-run が exit 0 で終わること。"""
        r = subprocess.run(
            [_py(), "-m", "tools.ai_orchestrator.run_review",
             "--task", "テスト", "--staged", "--dry-run"],
            capture_output=True, text=True, encoding="utf-8", cwd=REPO_ROOT,
        )
        assert r.returncode == 0, f"stderr: {r.stderr}"

    def test_generate_fail_still_exits_zero(self):
        """generate が exit 0 で返る場合（空 diff 等）run_review も exit 0。"""
        # 存在しないファイルを --files に渡すと diff が空になるが generate は exit 0
        r = subprocess.run(
            [_py(), "-m", "tools.ai_orchestrator.run_review",
             "--task", "テスト", "--files", "nonexistent_xyz.py"],
            capture_output=True, text=True, encoding="utf-8", cwd=REPO_ROOT,
        )
        assert r.returncode == 0, f"stderr: {r.stderr}"
