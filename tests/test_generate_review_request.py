# tests/test_generate_review_request.py
"""
generate_review_request.py の最小テスト。
- build_review_request: 純関数、mock 不要
- get_changed_files: --files 引数のパス、mock 不要
- get_git_diff: truncation ロジック（monkeypatch）
- run_test_command: 実コマンド（echo）
- CLI dry-run / output: subprocess
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tools.ai_orchestrator.generate_review_request import (
    build_review_request,
    get_changed_files,
    get_git_diff,
    run_test_command,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = REPO_ROOT / "venv" / "Scripts" / "python.exe"


# ──────────────────────────────────────────────────────────────────────────
# build_review_request（純関数）
# ──────────────────────────────────────────────────────────────────────────

class TestBuildReviewRequest:

    def test_minimal_has_only_required_keys(self):
        data = build_review_request(
            task="テスト", changed_files=["a.py"],
            git_diff="", test_command="", test_output="",
            open_questions=[], constraints=[],
        )
        assert data["task"] == "テスト"
        assert data["changed_files"] == ["a.py"]
        # 空値フィールドは key ごと除外される
        assert "git_diff" not in data
        assert "test_command" not in data
        assert "test_output" not in data
        assert "open_questions" not in data
        assert "constraints" not in data

    def test_git_diff_included_when_nonempty(self):
        data = build_review_request(
            task="t", changed_files=[],
            git_diff="diff --git a/foo.py ...", test_command="",
            test_output="", open_questions=[], constraints=[],
        )
        assert "git_diff" in data
        assert data["git_diff"] == "diff --git a/foo.py ..."

    def test_test_output_included_when_nonempty(self):
        data = build_review_request(
            task="t", changed_files=[],
            git_diff="", test_command="pytest",
            test_output="3 passed", open_questions=[], constraints=[],
        )
        assert data["test_command"] == "pytest"
        assert data["test_output"] == "3 passed"

    def test_open_questions_included(self):
        data = build_review_request(
            task="t", changed_files=[],
            git_diff="", test_command="", test_output="",
            open_questions=["疑問1", "疑問2"], constraints=[],
        )
        assert data["open_questions"] == ["疑問1", "疑問2"]

    def test_constraints_included(self):
        data = build_review_request(
            task="t", changed_files=[],
            git_diff="", test_command="", test_output="",
            open_questions=[], constraints=["制約1"],
        )
        assert data["constraints"] == ["制約1"]

    def test_empty_list_excluded(self):
        data = build_review_request(
            task="t", changed_files=[],
            git_diff="", test_command="", test_output="",
            open_questions=[], constraints=[],
        )
        assert "open_questions" not in data
        assert "constraints" not in data


# ──────────────────────────────────────────────────────────────────────────
# get_changed_files
# ──────────────────────────────────────────────────────────────────────────

class TestGetChangedFiles:

    def test_files_arg_bypasses_git(self):
        """--files 指定時は git を一切呼ばずそのまま返す。"""
        result = get_changed_files(staged=False, files=["foo.py", "bar.py"])
        assert result == ["foo.py", "bar.py"]

    def test_files_arg_staged_also_bypasses_git(self):
        result = get_changed_files(staged=True, files=["baz.py"])
        assert result == ["baz.py"]


# ──────────────────────────────────────────────────────────────────────────
# get_git_diff（truncation ロジック）
# ──────────────────────────────────────────────────────────────────────────

class TestGetGitDiffTruncation:

    def test_truncation_applied_over_limit(self, monkeypatch):
        long_diff = "\n".join([f"line{i}" for i in range(1001)])
        monkeypatch.setattr(
            "tools.ai_orchestrator.generate_review_request._git",
            lambda args: long_diff,
        )
        result = get_git_diff(staged=False, files=["x.py"])
        assert "[TRUNCATED:" in result
        # 最初の1000行は含まれる
        assert "line0" in result
        assert "line999" in result

    def test_no_truncation_under_limit(self, monkeypatch):
        short_diff = "\n".join([f"line{i}" for i in range(999)])
        monkeypatch.setattr(
            "tools.ai_orchestrator.generate_review_request._git",
            lambda args: short_diff,
        )
        result = get_git_diff(staged=False, files=["x.py"])
        assert "[TRUNCATED:" not in result

    def test_empty_diff_returns_empty(self, monkeypatch):
        monkeypatch.setattr(
            "tools.ai_orchestrator.generate_review_request._git",
            lambda args: "",
        )
        result = get_git_diff(staged=False, files=[])
        assert result == ""


# ──────────────────────────────────────────────────────────────────────────
# run_test_command
# ──────────────────────────────────────────────────────────────────────────

class TestRunTestCommand:

    def test_captures_stdout(self):
        """echo コマンドの出力が test_output に含まれること。"""
        output = run_test_command("echo hello_from_test")
        assert "hello_from_test" in output

    def test_captures_nonzero_exit(self):
        """失敗コマンドでも出力を返す（例外は出ない）。"""
        # exit 1 するコマンドでも結果文字列が返る
        output = run_test_command(
            f"{sys.executable} -c \"import sys; print('err_output'); sys.exit(1)\""
        )
        assert "err_output" in output


# ──────────────────────────────────────────────────────────────────────────
# CLI（subprocess）
# ──────────────────────────────────────────────────────────────────────────

class TestDryRunCLI:

    def _run(self, args: list[str], **kwargs) -> subprocess.CompletedProcess:
        return subprocess.run(
            [str(VENV_PYTHON), "-m", "tools.ai_orchestrator.generate_review_request"]
            + args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=REPO_ROOT,
            **kwargs,
        )

    def test_dry_run_exits_zero(self):
        result = self._run(["--task", "テスト", "--files", "rakuten_client.py", "--dry-run"])
        assert result.returncode == 0, f"stderr: {result.stderr}"

    def test_dry_run_prints_json(self):
        result = self._run(["--task", "my_task_value", "--files", "a.py", "--dry-run"])
        assert "my_task_value" in result.stdout

    def test_dry_run_no_file_created(self, tmp_path):
        output = tmp_path / "out.json"
        self._run([
            "--task", "テスト", "--files", "a.py",
            "--output", str(output), "--dry-run",
        ])
        assert not output.exists()

    def test_output_file_written(self, tmp_path):
        output = tmp_path / "review_request.json"
        result = self._run([
            "--task", "output_test_task",
            "--files", "rakuten_client.py",
            "--output", str(output),
        ])
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert output.exists()

    def test_output_contains_task(self, tmp_path):
        output = tmp_path / "review_request.json"
        self._run([
            "--task", "unique_task_name_xyz",
            "--files", "rakuten_client.py",
            "--output", str(output),
        ])
        data = json.loads(output.read_text(encoding="utf-8"))
        assert data["task"] == "unique_task_name_xyz"
        assert "rakuten_client.py" in data["changed_files"]

    def test_missing_task_exits_nonzero(self):
        result = self._run(["--files", "a.py"])
        assert result.returncode != 0

    def test_run_tests_populates_test_output(self, tmp_path):
        output = tmp_path / "review_request.json"
        self._run([
            "--task", "テスト",
            "--files", "rakuten_client.py",
            "--test-cmd", f"{sys.executable} -c \"print('test_marker_output')\"",
            "--run-tests",
            "--output", str(output),
        ])
        data = json.loads(output.read_text(encoding="utf-8"))
        assert "test_output" in data
        assert "test_marker_output" in data["test_output"]
