# tests/test_fill_result.py
"""
fill_result.py の最小テスト。
- _read_task_id: regex パース（monkeypatch）
- build_result_md: 純関数、mock 不要
- CLI dry-run / output: subprocess
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from tools.ai_orchestrator.fill_result import _read_task_id, build_result_md

REPO_ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = REPO_ROOT / "venv" / "Scripts" / "python.exe"


# ──────────────────────────────────────────────────────────────────────────
# _read_task_id
# ──────────────────────────────────────────────────────────────────────────

class TestReadTaskId:

    def test_reads_task_id(self, tmp_path, monkeypatch):
        task_md = tmp_path / "task.md"
        task_md.write_text('---\ntask_id: "0001"\ntitle: ""\n---\n', encoding="utf-8")
        import tools.ai_orchestrator.fill_result as mod
        monkeypatch.setattr(mod, "TASK_MD", task_md)
        assert mod._read_task_id() == "0001"

    def test_missing_returns_empty(self, tmp_path, monkeypatch):
        import tools.ai_orchestrator.fill_result as mod
        monkeypatch.setattr(mod, "TASK_MD", tmp_path / "nonexistent.md")
        assert mod._read_task_id() == ""

    def test_empty_task_id_returns_empty(self, tmp_path, monkeypatch):
        task_md = tmp_path / "task.md"
        task_md.write_text('---\ntask_id: ""\ntitle: ""\n---\n', encoding="utf-8")
        import tools.ai_orchestrator.fill_result as mod
        monkeypatch.setattr(mod, "TASK_MD", task_md)
        assert mod._read_task_id() == ""

    def test_unquoted_task_id(self, tmp_path, monkeypatch):
        task_md = tmp_path / "task.md"
        task_md.write_text('---\ntask_id: 0002\ntitle: ""\n---\n', encoding="utf-8")
        import tools.ai_orchestrator.fill_result as mod
        monkeypatch.setattr(mod, "TASK_MD", task_md)
        assert mod._read_task_id() == "0002"


# ──────────────────────────────────────────────────────────────────────────
# build_result_md
# ──────────────────────────────────────────────────────────────────────────

class TestBuildResultMd:

    def _build(self, **kwargs):
        defaults = dict(
            task_id="0001",
            generated_at="2026-03-30T12:00:00+09:00",
            conclusion="テスト変更",
            changed_files=["foo.py"],
            diff="diff --git a/foo.py b/foo.py",
            test_output="1 passed",
        )
        defaults.update(kwargs)
        return build_result_md(**defaults)

    def test_task_id_in_output(self):
        md = self._build()
        assert 'task_id: "0001"' in md

    def test_changed_files_in_output(self):
        md = self._build()
        assert "- foo.py" in md

    def test_diff_in_output(self):
        md = self._build()
        assert "diff --git a/foo.py" in md

    def test_test_output_in_output(self):
        md = self._build()
        assert "1 passed" in md

    def test_status_review_pending(self):
        md = self._build()
        assert "status: review-pending" in md

    def test_secrets_checked_false(self):
        md = self._build()
        assert "secrets_checked: false" in md

    def test_conclusion_in_output(self):
        md = self._build(conclusion="修正完了")
        assert "修正完了" in md

    def test_empty_conclusion_has_todo(self):
        md = self._build(conclusion="")
        assert "TODO" in md

    def test_empty_files_shows_dash(self):
        md = self._build(changed_files=[])
        # ファイルがない場合は "-" のみ
        assert "\n-\n" in md or "\n- \n" in md or "## 変更ファイル\n-" in md

    def test_generated_at_in_output(self):
        md = self._build(generated_at="2026-03-30T12:00:00+09:00")
        assert "2026-03-30T12:00:00+09:00" in md


# ──────────────────────────────────────────────────────────────────────────
# CLI（subprocess）
# ──────────────────────────────────────────────────────────────────────────

class TestDryRunCLI:

    def _run(self, args: list[str], **kwargs) -> subprocess.CompletedProcess:
        return subprocess.run(
            [str(VENV_PYTHON), "-m", "tools.ai_orchestrator.fill_result"] + args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=REPO_ROOT,
            **kwargs,
        )

    def test_dry_run_exits_zero(self):
        result = self._run(["--files", "rakuten_client.py", "--dry-run"])
        assert result.returncode == 0, f"stderr: {result.stderr}"

    def test_dry_run_no_file_created(self, tmp_path):
        out = tmp_path / "result.md"
        self._run(["--files", "rakuten_client.py", "--output", str(out), "--dry-run"])
        assert not out.exists()

    def test_output_file_written(self, tmp_path):
        out = tmp_path / "result.md"
        result = self._run(["--files", "rakuten_client.py", "--output", str(out)])
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert out.exists()

    def test_output_contains_task_id_field(self, tmp_path):
        out = tmp_path / "result.md"
        self._run(["--files", "rakuten_client.py", "--output", str(out)])
        text = out.read_text(encoding="utf-8")
        assert "task_id:" in text

    def test_output_contains_changed_file(self, tmp_path):
        out = tmp_path / "result.md"
        self._run(["--files", "rakuten_client.py", "--output", str(out)])
        text = out.read_text(encoding="utf-8")
        assert "rakuten_client.py" in text

    def test_conclusion_arg_in_output(self, tmp_path):
        out = tmp_path / "result.md"
        self._run([
            "--files", "rakuten_client.py",
            "--conclusion", "unique_conclusion_xyz",
            "--output", str(out),
        ])
        text = out.read_text(encoding="utf-8")
        assert "unique_conclusion_xyz" in text

    def test_status_review_pending_in_output(self, tmp_path):
        out = tmp_path / "result.md"
        self._run(["--files", "rakuten_client.py", "--output", str(out)])
        text = out.read_text(encoding="utf-8")
        assert "status: review-pending" in text
