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

from tools.ai_orchestrator.fill_result import (
    _build_conclusion_from_state,
    _build_concerns_from_state,
    _extract_gpt_concerns,
    _extract_log_summary,
    _read_open_questions,
    _read_task_id,
    _read_task_purpose,
    build_result_md,
)

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

    def test_concerns_todo_when_no_cycle_state(self):
        md = self._build()
        assert "## 未確定点・懸念" in md
        assert "TODO" in md

    def test_concerns_nashi_when_ng_history_empty(self):
        state = {"ng_history": [], "loops": []}
        md = self._build(cycle_state=state)
        assert "なし" in md
        assert "TODO" not in md.split("## 未確定点・懸念")[1].split("##")[0]

    def test_concerns_from_ng_history(self):
        state = {
            "ng_history": [
                {"reason": "テスト失敗: assertion error"},
                {"reason": "スコープ外変更"},
            ],
            "loops": [],
        }
        md = self._build(cycle_state=state)
        section = md.split("## 未確定点・懸念")[1].split("##")[0]
        assert "テスト失敗: assertion error" in section
        assert "スコープ外変更" in section

    def test_conclusion_from_cycle_state(self):
        state = {
            "ng_history": [],
            "loops": [{"summary": "XX を修正", "test_result": "pass"}],
        }
        md = self._build(conclusion="", cycle_state=state)
        assert "XX を修正" in md
        assert "テスト: pass" in md
        assert "TODO" not in md.split("## 結論")[1].split("##")[0]

    def test_conclusion_arg_overrides_cycle_state(self):
        state = {
            "ng_history": [],
            "loops": [{"summary": "XX を修正", "test_result": "pass"}],
        }
        md = self._build(conclusion="手書き結論", cycle_state=state)
        assert "手書き結論" in md
        assert "XX を修正" not in md.split("## 結論")[1].split("##")[0]

    def test_conclusion_todo_when_state_has_no_loops(self):
        state = {"ng_history": [], "loops": []}
        md = self._build(conclusion="", cycle_state=state)
        assert "TODO" in md.split("## 結論")[1].split("##")[0]

    def test_gpt_review_block_approve(self, tmp_path):
        """review_reply.md に approve があれば GPT レビュー結果ブロックが出る。"""
        reply = tmp_path / "review_reply.md"
        reply.write_text("## Decision\napprove\n", encoding="utf-8")
        md = self._build(review_reply_path=reply)
        assert "## GPT レビュー結果" in md
        assert "Decision: approve" in md

    def test_gpt_review_block_with_concerns(self, tmp_path):
        """懸念点セクションがあれば ### GPT 懸念点 として出る。"""
        reply = tmp_path / "review_reply.md"
        reply.write_text(
            "## Decision\napprove\n## 懸念（リスク）\nAPIキー漏洩リスクあり\n## 次\nなし\n",
            encoding="utf-8",
        )
        md = self._build(review_reply_path=reply)
        assert "### GPT 懸念点" in md
        assert "APIキー漏洩リスクあり" in md

    def test_gpt_review_block_absent_when_no_reply(self, tmp_path):
        """review_reply.md が存在しなければ GPT レビュー結果ブロック自体が出ない。"""
        md = self._build(review_reply_path=tmp_path / "nonexistent.md")
        assert "GPT レビュー結果" not in md

    def test_concerns_has_gpt_notice_when_reply_has_concerns(self, tmp_path):
        """GPT懸念あり + cycle_state あり → 未確定点に案内1行が入る。"""
        reply = tmp_path / "review_reply.md"
        reply.write_text("## 懸念（リスク）\nAPIキー漏洩リスク\n", encoding="utf-8")
        state = {"ng_history": [], "loops": []}
        md = self._build(cycle_state=state, review_reply_path=reply)
        section = md.split("## 未確定点・懸念")[1].split("##")[0]
        assert "GPTレビューで追加懸念あり" in section

    def test_concerns_no_gpt_notice_when_no_reply_concerns(self, tmp_path):
        """GPT懸念なし → 未確定点に案内は出ない。"""
        reply = tmp_path / "review_reply.md"
        reply.write_text("## Decision\napprove\n", encoding="utf-8")
        state = {"ng_history": [], "loops": []}
        md = self._build(cycle_state=state, review_reply_path=reply)
        section = md.split("## 未確定点・懸念")[1].split("##")[0]
        assert "GPTレビュー" not in section

    def test_conclusion_includes_commit_and_files(self):
        """cycle_state + changed_files → conclusion に commit と変更ファイルが入る。"""
        state = {
            "ng_history": [],
            "loops": [{"summary": "foo 修正", "test_result": "pass", "commit": "abc1234"}],
        }
        md = self._build(conclusion="", cycle_state=state, changed_files=["foo.py"])
        section = md.split("## 結論")[1].split("##")[0]
        assert "abc1234" in section
        assert "foo.py" in section


# ── _extract_gpt_concerns ─────────────────────────────────────────────────

class TestExtractGptConcerns:

    def test_concerns_section_extracted(self, tmp_path):
        f = tmp_path / "r.md"
        f.write_text("## 懸念（リスク）\nfoo bar\n## 次\nなし\n", encoding="utf-8")
        assert _extract_gpt_concerns(f) == "foo bar"

    def test_no_concerns_section_returns_empty(self, tmp_path):
        f = tmp_path / "r.md"
        f.write_text("## Decision\napprove\n", encoding="utf-8")
        assert _extract_gpt_concerns(f) == ""

    def test_missing_file_returns_empty(self, tmp_path):
        assert _extract_gpt_concerns(tmp_path / "nonexistent.md") == ""


# ── _extract_log_summary ─────────────────────────────────────────────────

class TestExtractLogSummary:

    def test_empty_returns_nashi(self):
        assert _extract_log_summary("") == "なし"

    def test_no_keywords_returns_nashi(self):
        assert _extract_log_summary("1 passed in 0.1s") == "なし"

    def test_warning_extracted(self):
        out = "line1\nWARNING: something\nline3"
        assert "WARNING: something" in _extract_log_summary(out)

    def test_error_extracted(self):
        out = "line1\nERROR: bad\nline3"
        assert "ERROR: bad" in _extract_log_summary(out)

    def test_failed_extracted(self):
        out = "FAILED tests/test_foo.py::test_bar\n1 failed"
        result = _extract_log_summary(out)
        assert "FAILED" in result
        assert "failed" in result

    def test_traceback_extracted(self):
        out = "Traceback (most recent call last):\n  File foo.py"
        assert "Traceback" in _extract_log_summary(out)

    def test_build_result_md_log_summary_filled(self):
        """build_result_md でログ要約欄が test_output から自動補完されること。"""
        md = build_result_md(
            task_id="0001",
            generated_at="2026-01-01T00:00:00+09:00",
            conclusion="test",
            changed_files=["foo.py"],
            diff="",
            test_output="FAILED tests/test_foo.py\n1 failed",
        )
        section = md.split("## ログ要約")[1].split("##")[0]
        assert "FAILED" in section
        assert "TODO" not in section

    def test_build_result_md_log_summary_nashi_when_no_output(self):
        """test_output が空のとき「なし」になること。"""
        md = build_result_md(
            task_id="0001",
            generated_at="2026-01-01T00:00:00+09:00",
            conclusion="test",
            changed_files=["foo.py"],
            diff="",
            test_output="",
        )
        section = md.split("## ログ要約")[1].split("##")[0]
        assert "なし" in section
        assert "TODO" not in section


# ── _build_conclusion_from_state ─────────────────────────────────────────

class TestBuildConclusionFromState:

    def test_returns_summary_and_test_result(self):
        state = {"loops": [{"summary": "foo を修正", "test_result": "pass"}]}
        assert _build_conclusion_from_state(state) == "foo を修正。テスト: pass。"

    def test_no_test_result_returns_summary_only(self):
        state = {"loops": [{"summary": "foo を修正", "test_result": ""}]}
        assert _build_conclusion_from_state(state) == "foo を修正。"

    def test_empty_loops_returns_empty(self):
        assert _build_conclusion_from_state({"loops": []}) == ""

    def test_uses_last_loop(self):
        state = {"loops": [
            {"summary": "first", "test_result": "pass"},
            {"summary": "second", "test_result": "fail"},
        ]}
        result = _build_conclusion_from_state(state)
        assert "second" in result
        assert "first" not in result

    def test_includes_commit_when_present(self):
        state = {"loops": [{"summary": "foo を修正", "test_result": "pass", "commit": "abc1234"}]}
        result = _build_conclusion_from_state(state)
        assert "abc1234" in result

    def test_includes_changed_files_from_arg(self):
        state = {"loops": [{"summary": "foo を修正", "test_result": "pass", "commit": ""}]}
        result = _build_conclusion_from_state(state, changed_files=["foo.py", "bar.py"])
        assert "foo.py" in result
        assert "bar.py" in result

    def test_no_commit_no_files_uses_summary_and_test(self):
        state = {"loops": [{"summary": "foo を修正", "test_result": "pass", "commit": ""}]}
        result = _build_conclusion_from_state(state)
        assert result == "foo を修正。テスト: pass。"


# ── _build_concerns_from_state ────────────────────────────────────────────

class TestBuildConcernsFromState:

    def test_empty_ng_history_returns_nashi(self):
        assert _build_concerns_from_state({"ng_history": []}) == "なし"

    def test_missing_ng_history_returns_nashi(self):
        assert _build_concerns_from_state({}) == "なし"

    def test_ng_history_returns_reason_list(self):
        state = {"ng_history": [
            {"reason": "テスト失敗"},
            {"reason": "スコープ外"},
        ]}
        result = _build_concerns_from_state(state)
        assert "- テスト失敗" in result
        assert "- スコープ外" in result

    def test_skips_empty_reason(self):
        state = {"ng_history": [{"reason": ""}, {"reason": "有効な理由"}]}
        result = _build_concerns_from_state(state)
        assert result == "- 有効な理由"

    def test_has_gpt_concerns_adds_notice(self):
        """has_gpt_concerns=True のとき案内1行が追加される。"""
        result = _build_concerns_from_state({"ng_history": []}, has_gpt_concerns=True)
        assert "GPTレビューで追加懸念あり" in result
        assert "## GPT レビュー結果" in result

    def test_has_gpt_concerns_combined_with_ng_history(self):
        """ng_history + GPT懸念の両方が出る。"""
        state = {"ng_history": [{"reason": "テスト失敗"}]}
        result = _build_concerns_from_state(state, has_gpt_concerns=True)
        assert "- テスト失敗" in result
        assert "GPTレビューで追加懸念あり" in result

    def test_no_gpt_concerns_no_notice(self):
        """has_gpt_concerns=False（デフォルト）では案内が出ない。"""
        state = {"ng_history": [{"reason": "テスト失敗"}]}
        result = _build_concerns_from_state(state)
        assert "GPTレビュー" not in result


# ── _read_open_questions ──────────────────────────────────────────────────

class TestReadOpenQuestions:

    def test_returns_questions(self, tmp_path):
        import json
        f = tmp_path / "review_request.json"
        f.write_text(json.dumps({"open_questions": ["疑問A", "疑問B"]}), encoding="utf-8")
        assert _read_open_questions(f) == ["疑問A", "疑問B"]

    def test_missing_file_returns_empty(self, tmp_path):
        assert _read_open_questions(tmp_path / "no.json") == []

    def test_no_open_questions_key_returns_empty(self, tmp_path):
        import json
        f = tmp_path / "review_request.json"
        f.write_text(json.dumps({"task": "foo"}), encoding="utf-8")
        assert _read_open_questions(f) == []

    def test_broken_json_returns_empty(self, tmp_path):
        f = tmp_path / "review_request.json"
        f.write_text("not json", encoding="utf-8")
        assert _read_open_questions(f) == []

    def test_empty_strings_filtered_out(self, tmp_path):
        import json
        f = tmp_path / "review_request.json"
        f.write_text(json.dumps({"open_questions": ["有効", "", "  "]}), encoding="utf-8")
        assert _read_open_questions(f) == ["有効"]

    def test_review_focus_from_open_questions_in_build(self, tmp_path):
        """open_questions が review_focus として build_result_md に渡ると出力に含まれること。"""
        result = build_result_md(
            task_id="0001",
            generated_at="2026-01-01T00:00:00+09:00",
            conclusion="テスト",
            changed_files=["foo.py"],
            diff="",
            test_output="",
            review_focus=["疑問A", "疑問B"],
        )
        assert "疑問A" in result
        assert "疑問B" in result
        assert "TODO" not in result.split("## 重点レビュー観点")[1].split("##")[0]


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

    def test_review_request_output_contains_metadata(self, tmp_path):
        out = tmp_path / "review_request.md"
        self._run(["--print-chat-prompt", "--review-request-output", str(out)])
        text = out.read_text(encoding="utf-8")
        assert "generated_at:" in text
        assert "template_version:" in text
