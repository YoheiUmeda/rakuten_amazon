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
    collect_related_code,
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

    def _build(self, **kwargs):
        defaults = dict(
            task="テスト", changed_files=["a.py"],
            git_diff="", test_command="", test_output="",
            related_code="", open_questions=[], constraints=[],
        )
        defaults.update(kwargs)
        return build_review_request(**defaults)

    def test_minimal_has_only_required_keys(self):
        data = self._build()
        assert data["task"] == "テスト"
        assert data["changed_files"] == ["a.py"]
        assert "git_diff" not in data
        assert "test_command" not in data
        assert "test_output" not in data
        assert "related_code" not in data
        assert "open_questions" not in data
        assert "constraints" not in data

    def test_git_diff_included_when_nonempty(self):
        data = self._build(git_diff="diff --git a/foo.py ...")
        assert "git_diff" in data
        assert data["git_diff"] == "diff --git a/foo.py ..."

    def test_test_output_included_when_nonempty(self):
        data = self._build(test_command="pytest", test_output="3 passed")
        assert data["test_command"] == "pytest"
        assert data["test_output"] == "3 passed"

    def test_related_code_included(self):
        data = self._build(related_code="def foo(): pass")
        assert "related_code" in data
        assert data["related_code"] == "def foo(): pass"

    def test_related_code_empty_excluded(self):
        data = self._build(related_code="")
        assert "related_code" not in data

    def test_open_questions_included(self):
        data = self._build(open_questions=["疑問1", "疑問2"])
        assert data["open_questions"] == ["疑問1", "疑問2"]

    def test_constraints_included(self):
        data = self._build(constraints=["制約1"])
        assert data["constraints"] == ["制約1"]

    def test_empty_list_excluded(self):
        data = self._build()
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

    def test_related_code_in_output(self, tmp_path):
        """--related-code で実ファイルを指定すると JSON に related_code が含まれる。"""
        # rakuten_client.py は存在するファイル
        output = tmp_path / "review_request.json"
        result = self._run([
            "--task", "テスト",
            "--files", "rakuten_client.py",
            "--related-code", "rakuten_client.py",
            "--output", str(output),
        ])
        assert result.returncode == 0, f"stderr: {result.stderr}"
        data = json.loads(output.read_text(encoding="utf-8"))
        assert "related_code" in data
        assert "rakuten_client.py" in data["related_code"]


# ──────────────────────────────────────────────────────────────────────────
# collect_related_code
# ──────────────────────────────────────────────────────────────────────────

class TestCollectRelatedCode:

    def test_empty_files_returns_empty(self):
        result = collect_related_code([])
        assert result == ""

    def test_single_file_included(self, tmp_path, monkeypatch):
        src = tmp_path / "sample.py"
        src.write_text("def hello(): pass\n", encoding="utf-8")
        # REPO_ROOT を tmp_path に向ける
        import tools.ai_orchestrator.generate_review_request as mod
        monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)
        result = collect_related_code(["sample.py"])
        assert "def hello(): pass" in result
        assert "sample.py" in result

    def test_missing_file_skipped(self):
        # 存在しないファイルは例外なく空文字列を返す
        result = collect_related_code(["nonexistent_file_xyz.py"])
        assert result == ""

    def test_per_file_truncation(self, tmp_path, monkeypatch):
        src = tmp_path / "big.py"
        src.write_text("\n".join([f"line{i}" for i in range(201)]), encoding="utf-8")
        import tools.ai_orchestrator.generate_review_request as mod
        monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)
        result = collect_related_code(["big.py"], per_file_lines=200)
        assert "[TRUNCATED:" in result
        assert "line0" in result
        assert "line199" in result  # 200行目（0-indexed 199）は含まれる

    def test_total_char_limit(self, tmp_path, monkeypatch):
        src = tmp_path / "large.py"
        src.write_text("x" * 5000, encoding="utf-8")  # 5000文字
        import tools.ai_orchestrator.generate_review_request as mod
        monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)
        result = collect_related_code(["large.py"], total_chars=4000)
        assert "[TRUNCATED: total chars exceeded 4000]" in result
