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

from tools.ai_orchestrator.fill_result import _read_task_id, _read_task_purpose, build_result_md

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
# _read_task_purpose
# ──────────────────────────────────────────────────────────────────────────

class TestReadTaskPurpose:

    def _write_task(self, tmp_path, body: str) -> Path:
        task_md = tmp_path / "task.md"
        task_md.write_text(
            f"---\ntask_id: \"0001\"\n---\n{body}",
            encoding="utf-8",
        )
        return task_md

    def test_reads_task_section(self, tmp_path, monkeypatch):
        task_md = self._write_task(tmp_path, "\n## タスク\nXX を修正する\n\n## 背景と目的\nyyy\n")
        import tools.ai_orchestrator.fill_result as mod
        monkeypatch.setattr(mod, "TASK_MD", task_md)
        assert mod._read_task_purpose() == "XX を修正する"

    def test_missing_file_returns_empty(self, tmp_path, monkeypatch):
        import tools.ai_orchestrator.fill_result as mod
        monkeypatch.setattr(mod, "TASK_MD", tmp_path / "nonexistent.md")
        assert mod._read_task_purpose() == ""

    def test_empty_task_section_returns_empty(self, tmp_path, monkeypatch):
        task_md = self._write_task(tmp_path, "\n## タスク\n\n## 背景と目的\nyyy\n")
        import tools.ai_orchestrator.fill_result as mod
        monkeypatch.setattr(mod, "TASK_MD", task_md)
        assert mod._read_task_purpose() == ""

    def test_does_not_match_task_details(self, tmp_path, monkeypatch):
        """## タスク詳細 は ## タスク に誤マッチしないこと。"""
        task_md = self._write_task(tmp_path, "\n## タスク詳細\nXX\n\n## タスク\n本物の目的\n")
        import tools.ai_orchestrator.fill_result as mod
        monkeypatch.setattr(mod, "TASK_MD", task_md)
        assert mod._read_task_purpose() == "本物の目的"

    def test_does_not_match_task_list(self, tmp_path, monkeypatch):
        """## タスク一覧 だけのとき は "" を返すこと。"""
        task_md = self._write_task(tmp_path, "\n## タスク一覧\nYY\n")
        import tools.ai_orchestrator.fill_result as mod
        monkeypatch.setattr(mod, "TASK_MD", task_md)
        assert mod._read_task_purpose() == ""

    def test_frontmatter_hash_not_mistaken_for_section(self, tmp_path, monkeypatch):
        """フロントマター内の # コメントを ## タスク と誤認しないこと。"""
        task_md = tmp_path / "task.md"
        task_md.write_text(
            "---\ntask_id: \"0001\"\n# status の定義:\n---\n\n## タスク\n正しい目的\n\n## 背景\nyyy\n",
            encoding="utf-8",
        )
        import tools.ai_orchestrator.fill_result as mod
        monkeypatch.setattr(mod, "TASK_MD", task_md)
        assert mod._read_task_purpose() == "正しい目的"


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

    def test_purpose_in_output(self):
        md = self._build(purpose="XX 機能の修正")
        assert "XX 機能の修正" in md

    def test_empty_purpose_has_todo(self):
        md = self._build(purpose="")
        assert "## 目的" in md
        assert "TODO" in md

    def test_review_focus_in_output(self):
        md = self._build(review_focus=["ロジックの正確性", "副作用の有無"])
        assert "ロジックの正確性" in md
        assert "副作用の有無" in md

    def test_empty_review_focus_has_todo(self):
        md = self._build(review_focus=[])
        assert "## 重点レビュー観点" in md
        assert "TODO" in md

    def test_impact_scope_section_exists(self):
        md = self._build()
        assert "## 影響範囲" in md


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

    def test_purpose_arg_in_output(self, tmp_path):
        out = tmp_path / "result.md"
        self._run(["--files", "rakuten_client.py", "--purpose", "unique_purpose_xyz", "--output", str(out)])
        assert "unique_purpose_xyz" in out.read_text(encoding="utf-8")

    def test_review_focus_arg_in_output(self, tmp_path):
        out = tmp_path / "result.md"
        self._run(["--files", "rakuten_client.py", "--review-focus", "観点A", "観点B", "--output", str(out)])
        text = out.read_text(encoding="utf-8")
        assert "観点A" in text
        assert "観点B" in text

    def test_print_chat_prompt_contains_url(self):
        """--print-chat-prompt の stdout に GitHub URL が含まれること。"""
        result = self._run(["--print-chat-prompt"])
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "github.com/YoheiUmeda/rakuten_amazon" in result.stdout
        assert "result.md" in result.stdout

    def test_print_chat_prompt_contains_instruction(self):
        """--print-chat-prompt の stdout にレビュー指示文が含まれること。"""
        result = self._run(["--print-chat-prompt"])
        assert "secrets" in result.stdout
        assert "Approve" in result.stdout

    def test_review_request_output_creates_file(self, tmp_path):
        out = tmp_path / "review_request.md"
        result = self._run(["--print-chat-prompt", "--review-request-output", str(out)])
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert out.exists()

    def test_review_request_output_contains_url(self, tmp_path):
        out = tmp_path / "review_request.md"
        self._run(["--print-chat-prompt", "--review-request-output", str(out)])
        text = out.read_text(encoding="utf-8")
        assert "github.com/YoheiUmeda/rakuten_amazon" in text

    def test_review_request_output_contains_instruction(self, tmp_path):
        out = tmp_path / "review_request.md"
        self._run(["--print-chat-prompt", "--review-request-output", str(out)])
        text = out.read_text(encoding="utf-8")
        assert "Approve" in text
