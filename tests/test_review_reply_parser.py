# tests/test_review_reply_parser.py
"""review_reply_parser.py の最小テスト。"""
from __future__ import annotations

from pathlib import Path

from tools.ai_orchestrator.review_reply_parser import read_decision, read_concerns


class TestReadDecision:

    def test_approve(self, tmp_path):
        f = tmp_path / "r.md"
        f.write_text("## Decision\napprove\n", encoding="utf-8")
        assert read_decision(f) == "approve"

    def test_request_changes(self, tmp_path):
        f = tmp_path / "r.md"
        f.write_text("## Decision\nrequest_changes\n", encoding="utf-8")
        assert read_decision(f) == "request_changes"

    def test_heading_ignored(self, tmp_path):
        f = tmp_path / "r.md"
        f.write_text("# approve\n## request_changes\n", encoding="utf-8")
        assert read_decision(f) == ""

    def test_missing_file_returns_empty(self, tmp_path):
        assert read_decision(tmp_path / "nonexistent.md") == ""

    def test_no_keyword_returns_empty(self, tmp_path):
        f = tmp_path / "r.md"
        f.write_text("## 事実\nなし\n", encoding="utf-8")
        assert read_decision(f) == ""

    def test_case_insensitive(self, tmp_path):
        f = tmp_path / "r.md"
        f.write_text("APPROVE\n", encoding="utf-8")
        assert read_decision(f) == "approve"


class TestReadConcerns:

    def test_concerns_section_extracted(self, tmp_path):
        f = tmp_path / "r.md"
        f.write_text("## 懸念（リスク）\nfoo bar\n## 次\nなし\n", encoding="utf-8")
        assert read_concerns(f) == "foo bar"

    def test_no_concerns_section_returns_empty(self, tmp_path):
        f = tmp_path / "r.md"
        f.write_text("## Decision\napprove\n", encoding="utf-8")
        assert read_concerns(f) == ""

    def test_missing_file_returns_empty(self, tmp_path):
        assert read_concerns(tmp_path / "nonexistent.md") == ""

    def test_multiline_concerns(self, tmp_path):
        f = tmp_path / "r.md"
        f.write_text("## 懸念点\nline1\nline2\n## 次\nなし\n", encoding="utf-8")
        result = read_concerns(f)
        assert "line1" in result
        assert "line2" in result
