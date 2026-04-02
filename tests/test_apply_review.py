# tests/test_apply_review.py
from pathlib import Path

import tools.ai_orchestrator.apply_review as mod
from tools.ai_orchestrator.apply_review import _parse_decision, _parse_section, apply_review

APPROVE_REPLY = """\
## Decision
Approve

## Issues
なし

## Required changes
なし

## Notes
"""

REQUEST_REPLY = """\
## Decision
Request changes

## Issues
- テストが不足している

## Required changes
- foo.py にテストを追加する

## Notes
"""


class TestParseSection:

    def test_reads_decision(self):
        assert _parse_section(APPROVE_REPLY, "Decision") == "Approve"

    def test_reads_required_changes(self):
        assert _parse_section(REQUEST_REPLY, "Required changes") == "- foo.py にテストを追加する"

    def test_missing_section_returns_empty(self):
        assert _parse_section(APPROVE_REPLY, "Nonexistent") == ""


class TestParseDecision:

    def test_approve(self):
        assert _parse_decision(APPROVE_REPLY) == "approve"

    def test_request_changes(self):
        assert _parse_decision(REQUEST_REPLY) == "request_changes"

    def test_empty_decision_returns_empty(self):
        assert _parse_decision("## Decision\n\n## Issues\n") == ""

    def test_case_insensitive(self):
        text = "## Decision\nAPPROVE\n## Issues\n"
        assert _parse_decision(text) == "approve"


class TestApplyReview:

    def _make_result(self, tmp_path: Path, status: str = "review-pending") -> Path:
        p = tmp_path / "result.md"
        p.write_text(f"---\nstatus: {status}\n---\n", encoding="utf-8")
        return p

    def _make_reply(self, tmp_path: Path, content: str) -> Path:
        p = tmp_path / "review_reply.md"
        p.write_text(content, encoding="utf-8")
        return p

    def test_approve_updates_status(self, tmp_path):
        reply = self._make_reply(tmp_path, APPROVE_REPLY)
        result = self._make_result(tmp_path)
        rc = apply_review(reply, result, dry_run=False)
        assert rc == 0
        assert "status: reviewed" in result.read_text(encoding="utf-8")

    def test_approve_dry_run_no_change(self, tmp_path):
        reply = self._make_reply(tmp_path, APPROVE_REPLY)
        result = self._make_result(tmp_path)
        apply_review(reply, result, dry_run=True)
        assert "status: review-pending" in result.read_text(encoding="utf-8")

    def test_request_changes_no_update(self, tmp_path):
        reply = self._make_reply(tmp_path, REQUEST_REPLY)
        result = self._make_result(tmp_path)
        rc = apply_review(reply, result, dry_run=False)
        assert rc == 0
        assert "status: review-pending" in result.read_text(encoding="utf-8")

    def test_missing_reply_returns_error(self, tmp_path):
        rc = apply_review(tmp_path / "nonexistent.md", tmp_path / "result.md")
        assert rc == 1

    def test_empty_decision_returns_error(self, tmp_path):
        reply = self._make_reply(tmp_path, "## Decision\n\n## Issues\n")
        result = self._make_result(tmp_path)
        rc = apply_review(reply, result)
        assert rc == 1

    def test_auto_approve_calls_cycle_approve(self, tmp_path, monkeypatch):
        """auto_approve=True + approve → _run_cycle_approve が呼ばれる。"""
        called = []
        monkeypatch.setattr(mod, "_run_cycle_approve", lambda: called.append(True) or True)
        reply = self._make_reply(tmp_path, APPROVE_REPLY)
        result = self._make_result(tmp_path)
        apply_review(reply, result, dry_run=False, auto_approve=True)
        assert called

    def test_auto_approve_skipped_on_dry_run(self, tmp_path, monkeypatch):
        """dry_run=True のとき _run_cycle_approve は呼ばれない。"""
        called = []
        monkeypatch.setattr(mod, "_run_cycle_approve", lambda: called.append(True) or True)
        reply = self._make_reply(tmp_path, APPROVE_REPLY)
        result = self._make_result(tmp_path)
        apply_review(reply, result, dry_run=True, auto_approve=True)
        assert not called

    def test_auto_approve_skipped_on_request_changes(self, tmp_path, monkeypatch):
        """decision=request_changes のとき _run_cycle_approve は呼ばれない。"""
        called = []
        monkeypatch.setattr(mod, "_run_cycle_approve", lambda: called.append(True) or True)
        reply = self._make_reply(tmp_path, REQUEST_REPLY)
        result = self._make_result(tmp_path)
        apply_review(reply, result, dry_run=False, auto_approve=True)
        assert not called

    def test_auto_approve_failure_returns_zero(self, tmp_path, monkeypatch):
        """_run_cycle_approve 失敗時も rc=0 で返る（fail-open）。"""
        monkeypatch.setattr(mod, "_run_cycle_approve", lambda: False)
        reply = self._make_reply(tmp_path, APPROVE_REPLY)
        result = self._make_result(tmp_path)
        rc = apply_review(reply, result, dry_run=False, auto_approve=True)
        assert rc == 0
