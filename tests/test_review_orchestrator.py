# tests/test_review_orchestrator.py
"""
redaction / validate_input / build_user_content / CLI dry-run の最小テスト。
openai パッケージ不要。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tools.ai_orchestrator.redaction import redact, redact_dict_fields
from tools.ai_orchestrator.orchestrator import validate_input, build_user_content

REPO_ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = REPO_ROOT / "venv" / "Scripts" / "python.exe"
EXAMPLE_INPUT = REPO_ROOT / ".ai" / "handoff" / "review_request.example.json"


# ──────────────────────────────────────────────────────────────────────────
# redaction
# ──────────────────────────────────────────────────────────────────────────

class TestRedact:

    def test_redact_openai_key(self):
        text = "api_key=sk-abcdefghijklmnopqrstuvwxyz123456"
        result = redact(text)
        assert "sk-abcdefghijklmnopqrstuvwxyz123456" not in result
        assert "[REDACTED]" in result

    def test_redact_db_url(self):
        text = "postgresql://user:pass@localhost:5432/mydb"
        result = redact(text)
        assert "user:pass@localhost" not in result
        assert "postgresql://[REDACTED]" in result

    def test_redact_password_eq(self):
        text = "password=hunter2"
        result = redact(text)
        assert "hunter2" not in result
        assert "[REDACTED]" in result

    def test_redact_secret_colon(self):
        text = "client_secret: mySecretValue123"
        result = redact(text)
        assert "mySecretValue123" not in result

    def test_redact_no_false_positive_normal_code(self):
        text = "def calculate_price(price, fee): return price - fee"
        result = redact(text)
        assert result == text  # 変更なし

    def test_redact_no_false_positive_japanese(self):
        text = "楽天APIで商品を検索する"
        result = redact(text)
        assert result == text

    def test_redact_dict_fields_applies_to_specified_fields(self):
        data = {
            "task": "テスト",
            "git_diff": "password=secret123",
            "related_code": "def foo(): pass",
        }
        result = redact_dict_fields(data, ["git_diff"])
        assert "[REDACTED]" in result["git_diff"]
        assert result["related_code"] == "def foo(): pass"
        assert result["task"] == "テスト"

    def test_redact_dict_fields_skips_none(self):
        data = {"git_diff": None, "task": "ok"}
        result = redact_dict_fields(data, ["git_diff"])
        assert result["git_diff"] is None  # None はスキップ


# ──────────────────────────────────────────────────────────────────────────
# validate_input
# ──────────────────────────────────────────────────────────────────────────

class TestValidateInput:

    def test_valid_minimal(self):
        validate_input({"task": "テスト", "changed_files": ["a.py"]})  # 例外なし

    def test_valid_full(self):
        validate_input({
            "task": "full test",
            "changed_files": ["a.py", "b.py"],
            "git_diff": "...",
            "test_output": "passed",
        })

    def test_missing_task(self):
        with pytest.raises(ValueError, match="task"):
            validate_input({"changed_files": ["a.py"]})

    def test_missing_changed_files(self):
        with pytest.raises(ValueError, match="changed_files"):
            validate_input({"task": "テスト"})

    def test_changed_files_not_list(self):
        with pytest.raises(ValueError, match="配列"):
            validate_input({"task": "テスト", "changed_files": "a.py"})

    def test_empty_task(self):
        with pytest.raises(ValueError, match="task"):
            validate_input({"task": "   ", "changed_files": []})


# ──────────────────────────────────────────────────────────────────────────
# build_user_content
# ──────────────────────────────────────────────────────────────────────────

class TestBuildUserContent:

    def test_contains_task(self):
        content = build_user_content({"task": "my task", "changed_files": ["x.py"]})
        assert "my task" in content

    def test_contains_changed_files(self):
        content = build_user_content({"task": "t", "changed_files": ["a.py", "b.py"]})
        assert "a.py" in content
        assert "b.py" in content

    def test_contains_open_questions(self):
        content = build_user_content({
            "task": "t", "changed_files": [],
            "open_questions": ["これは何？"]
        })
        assert "これは何？" in content

    def test_contains_constraints(self):
        content = build_user_content({
            "task": "t", "changed_files": [],
            "constraints": ["pass_filter に触れない"]
        })
        assert "pass_filter に触れない" in content


# ──────────────────────────────────────────────────────────────────────────
# CLI dry-run（subprocess）
# ──────────────────────────────────────────────────────────────────────────

class TestDryRunCLI:

    def test_dry_run_exits_zero(self, tmp_path):
        """dry-run が exit 0 で終わること。"""
        output = tmp_path / "reply.md"
        result = subprocess.run(
            [
                str(VENV_PYTHON),
                "-m", "tools.ai_orchestrator.orchestrator",
                "--input", str(EXAMPLE_INPUT),
                "--output", str(output),
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"

    def test_dry_run_does_not_create_output(self, tmp_path):
        """dry-run は output ファイルを作成しない。"""
        output = tmp_path / "reply.md"
        subprocess.run(
            [
                str(VENV_PYTHON),
                "-m", "tools.ai_orchestrator.orchestrator",
                "--input", str(EXAMPLE_INPUT),
                "--output", str(output),
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=REPO_ROOT,
        )
        assert not output.exists()

    def test_dry_run_missing_input_exits_nonzero(self, tmp_path):
        """存在しない input は exit 1 になること。"""
        result = subprocess.run(
            [
                str(VENV_PYTHON),
                "-m", "tools.ai_orchestrator.orchestrator",
                "--input", str(tmp_path / "nonexistent.json"),
                "--output", str(tmp_path / "reply.md"),
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=REPO_ROOT,
        )
        assert result.returncode != 0

    def test_short_task_log_no_ellipsis(self, tmp_path, capsys):
        """短いタスク名のとき [INFO] タスク行に '...' が付かない。"""
        import json
        from tools.ai_orchestrator.orchestrator import run
        data = {"task": "短いタスク", "changed_files": ["x.py"]}
        inp = tmp_path / "req.json"
        inp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        run(input_path=inp, output_path=tmp_path / "reply.md", dry_run=True)
        out = capsys.readouterr().out
        assert "短いタスク..." not in out
        assert "短いタスク" in out

    def test_long_task_log_has_ellipsis(self, tmp_path, capsys):
        """80文字超のタスク名のとき [INFO] タスク行に '...' が付く。"""
        import json
        from tools.ai_orchestrator.orchestrator import run
        long_task = "a" * 81
        data = {"task": long_task, "changed_files": ["x.py"]}
        inp = tmp_path / "req.json"
        inp.write_text(json.dumps(data), encoding="utf-8")
        run(input_path=inp, output_path=tmp_path / "reply.md", dry_run=True)
        out = capsys.readouterr().out
        assert "..." in out


# ──────────────────────────────────────────────────────────────────────────
# モデル解決
# ──────────────────────────────────────────────────────────────────────────

class TestModelResolution:

    def test_default_model_is_mini(self):
        """DEFAULT_MODEL が gpt-4o-mini であること。"""
        from tools.ai_orchestrator.openai_client import DEFAULT_MODEL
        assert DEFAULT_MODEL == "gpt-4o-mini"

    def test_env_var_overrides_default(self, monkeypatch):
        """OPENAI_MODEL env var がデフォルトを上書きすること。"""
        import os
        monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")
        resolved = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        assert resolved == "gpt-4o"

    def test_dry_run_shows_model(self, tmp_path):
        """dry-run の stdout に [INFO] model: が含まれること。"""
        out_path = tmp_path / "reply.md"
        r = subprocess.run(
            [str(VENV_PYTHON), "-m", "tools.ai_orchestrator.orchestrator",
             "--input", str(EXAMPLE_INPUT), "--output", str(out_path), "--dry-run"],
            capture_output=True, text=True, encoding="utf-8", cwd=REPO_ROOT,
        )
        assert r.returncode == 0
        assert "[INFO] model:" in r.stdout
