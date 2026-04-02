# tests/test_review_summary.py
"""review_summary.py の最小テスト。"""
from __future__ import annotations

from pathlib import Path

import pytest

from tools.ai_orchestrator.review_summary import (
    _read_review_decision,
    build_next_instruction_draft,
    build_summary,
)


# ── fixtures ─────────────────────────────────────────────────────────────────

def _state(status="done", goal="テストゴール", ng_history=None, loops=None):
    return {
        "status": status,
        "goal": goal,
        "ng_history": ng_history if ng_history is not None else [],
        "loops": loops if loops is not None else [
            {"loop_id": 1, "summary": "XX を修正", "test_result": "pass",
             "changed_files": ["src/foo.py"], "pre_commit": "abc0001", "commit": "abc0002"}
        ],
    }


# ── _read_review_decision ────────────────────────────────────────────────────

class TestReadReviewDecision:

    def test_approve_line(self, tmp_path):
        f = tmp_path / "review_reply.md"
        f.write_text("Approve — 問題なし\n", encoding="utf-8")
        assert _read_review_decision(f) == "approve"

    def test_request_changes_line(self, tmp_path):
        f = tmp_path / "review_reply.md"
        f.write_text("Request changes — テストが不足\n", encoding="utf-8")
        assert _read_review_decision(f) == "request_changes"

    def test_heading_approve_request_changes_ignored(self, tmp_path):
        """'## Approve / Request changes' の見出し行だけなら '' を返す。"""
        f = tmp_path / "review_reply.md"
        f.write_text("## Approve / Request changes\n（理由1行）\n", encoding="utf-8")
        assert _read_review_decision(f) == ""

    def test_heading_then_approve_decision(self, tmp_path):
        """見出し行 '## Approve / Request changes' の後に Approve 行がある → approve。"""
        f = tmp_path / "review_reply.md"
        f.write_text(
            "## Approve / Request changes\nApprove — 問題なし\n",
            encoding="utf-8",
        )
        assert _read_review_decision(f) == "approve"

    def test_heading_then_request_changes_decision(self, tmp_path):
        """見出し行の後に Request changes 行がある → request_changes。"""
        f = tmp_path / "review_reply.md"
        f.write_text(
            "## Approve / Request changes\nRequest changes — テスト不足\n",
            encoding="utf-8",
        )
        assert _read_review_decision(f) == "request_changes"

    def test_missing_file_returns_empty(self, tmp_path):
        assert _read_review_decision(tmp_path / "nonexistent.md") == ""

    def test_no_decision_keyword_returns_empty(self, tmp_path):
        f = tmp_path / "review_reply.md"
        f.write_text("コメントだけ\n説明文\n", encoding="utf-8")
        assert _read_review_decision(f) == ""

    def test_inline_approve_text_not_matched(self, tmp_path):
        """行中に 'approve' が含まれても行頭でなければ '' を返す。"""
        f = tmp_path / "review_reply.md"
        f.write_text("これは approve に関する説明です。\n", encoding="utf-8")
        assert _read_review_decision(f) == ""

    def test_case_insensitive(self, tmp_path):
        f = tmp_path / "review_reply.md"
        f.write_text("APPROVE — OK\n", encoding="utf-8")
        assert _read_review_decision(f) == "approve"


# ── build_next_instruction_draft ──────────────────────────────────────────────

class TestBuildNextInstructionDraft:

    def test_done_no_ng_shows_complete(self, tmp_path):
        draft = build_next_instruction_draft(_state(status="done"), tmp_path / "no.md")
        assert "✅ 完了" in draft
        assert "テストゴール" in draft

    def test_done_includes_changed_files(self, tmp_path):
        draft = build_next_instruction_draft(_state(status="done"), tmp_path / "no.md")
        assert "src/foo.py" in draft

    def test_done_includes_last_summary(self, tmp_path):
        draft = build_next_instruction_draft(_state(status="done"), tmp_path / "no.md")
        assert "XX を修正" in draft

    def test_ng_history_shows_fix_needed(self, tmp_path):
        state = _state(status="pending_review", ng_history=[
            {"reason": "テスト失敗: assertion error", "timestamp": "2026-01-01T00:00:00+09:00"},
        ])
        draft = build_next_instruction_draft(state, tmp_path / "no.md")
        assert "⚠️ 修正必要" in draft
        assert "テスト失敗: assertion error" in draft

    def test_request_changes_without_ng_history(self, tmp_path):
        reply = tmp_path / "review_reply.md"
        reply.write_text("Request changes — 網羅率が低い", encoding="utf-8")
        state = _state(status="pending_review")
        draft = build_next_instruction_draft(state, reply)
        assert "⚠️ 修正必要" in draft
        assert "review_reply.md" in draft

    def test_pending_no_ng_shows_waiting(self, tmp_path):
        state = _state(status="pending_review")
        draft = build_next_instruction_draft(state, tmp_path / "no.md")
        assert "⏳ レビュー待ち" in draft
        assert "approve" in draft

    def test_approve_in_review_reply_keeps_done(self, tmp_path):
        reply = tmp_path / "review_reply.md"
        reply.write_text("Approve — 問題なし", encoding="utf-8")
        draft = build_next_instruction_draft(_state(status="done"), reply)
        assert "✅ 完了" in draft

    def test_done_with_request_changes_shows_fix(self, tmp_path):
        """status=done でも review_reply が Request changes なら修正必要を表示する。"""
        reply = tmp_path / "review_reply.md"
        reply.write_text("Request changes — 修正が必要", encoding="utf-8")
        draft = build_next_instruction_draft(_state(status="done"), reply)
        assert "⚠️ 修正必要" in draft

    def test_no_loops_handles_gracefully(self, tmp_path):
        state = _state(status="done", loops=[])
        draft = build_next_instruction_draft(state, tmp_path / "no.md")
        assert "なし" in draft or "(なし)" in draft

    def test_output_has_required_sections(self, tmp_path):
        draft = build_next_instruction_draft(_state(), tmp_path / "no.md")
        for section in ["## ステータス", "## 次のアクション", "## 対象ファイル",
                        "## 直近ループの要約", "## 修正理由 / 懸念点"]:
            assert section in draft

    def test_stopped_shows_stopped_label(self, tmp_path):
        state = _state(status="stopped")
        state["stop_reason"] = "スコープ外変更が検出された"
        draft = build_next_instruction_draft(state, tmp_path / "no.md")
        assert "⛔ 作業停止" in draft
        assert "スコープ外変更が検出された" in draft


# ── build_summary ─────────────────────────────────────────────────────────────

class TestBuildSummary:

    def _base_state(self):
        return {
            "status": "pending_review",
            "goal": "テストゴール",
            "cycle_id": "20260101-000000",
            "loop_count": 1,
            "base_commit": "abc0001",
            "last_good_commit": "abc0002",
            "ng_history": [],
            "loops": [
                {
                    "loop_id": 1,
                    "timestamp": "2026-01-01T00:00:00",
                    "test_result": "pass",
                    "commit": "abc0002",
                    "pre_commit": "abc0001",
                    "changed_files": ["src/foo.py"],
                    "summary": "foo を修正",
                }
            ],
        }

    def test_test_log_path_shown_when_provided(self):
        state = self._base_state()
        content = build_summary(state, test_log_path=".ai/logs/test_abc0001_pass_20260101.log")
        assert "テストログ: .ai/logs/test_abc0001_pass_20260101.log" in content

    def test_test_log_path_absent_when_empty(self):
        state = self._base_state()
        content = build_summary(state)
        assert "テストログ" not in content
