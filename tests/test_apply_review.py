# tests/test_apply_review.py
from pathlib import Path

import tools.ai_orchestrator.apply_review as mod
from tools.ai_orchestrator.apply_review import (
    _archive_task, _extract_reject_reason, _parse_decision, _parse_section, apply_review,
)

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


class TestExtractRejectReason:

    def test_required_changes_first(self):
        """Required changes の先頭箇条書きを優先する。"""
        assert _extract_reject_reason(REQUEST_REPLY) == "foo.py にテストを追加する"

    def test_falls_back_to_issues(self):
        """Required changes が空なら Issues の先頭箇条書きを返す。"""
        text = "## Decision\nrequest_changes\n## Issues\n- 問題点A\n## Required changes\n\n"
        assert _extract_reject_reason(text) == "問題点A"

    def test_default_when_both_empty(self):
        """両セクションが空ならデフォルト文字列を返す。"""
        assert _extract_reject_reason(APPROVE_REPLY) == "request_changes by AI review"


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

    def test_auto_archive_runs_when_approve_succeeds(self, tmp_path, monkeypatch):
        """auto_approve 成功 + auto_archive=True → _archive_task が呼ばれる。"""
        monkeypatch.setattr(mod, "_run_cycle_approve", lambda: True)
        called = []
        monkeypatch.setattr(mod, "_archive_task", lambda t, a: called.append(True) or True)
        monkeypatch.setattr(mod, "TASK_MD", tmp_path / "task.md")
        monkeypatch.setattr(mod, "ARCHIVE_DIR", tmp_path / "archive")
        reply = self._make_reply(tmp_path, APPROVE_REPLY)
        result = self._make_result(tmp_path)
        apply_review(reply, result, dry_run=False, auto_approve=True, auto_archive=True)
        assert called

    def test_auto_archive_skipped_on_approve_failure(self, tmp_path, monkeypatch):
        """cycle_manager approve 失敗時は _archive_task を呼ばない。"""
        monkeypatch.setattr(mod, "_run_cycle_approve", lambda: False)
        called = []
        monkeypatch.setattr(mod, "_archive_task", lambda t, a: called.append(True) or True)
        reply = self._make_reply(tmp_path, APPROVE_REPLY)
        result = self._make_result(tmp_path)
        apply_review(reply, result, dry_run=False, auto_approve=True, auto_archive=True)
        assert not called

    def test_auto_archive_requires_auto_approve(self, tmp_path, monkeypatch):
        """--auto-archive 単独（auto_approve なし）では _archive_task を呼ばない。"""
        called = []
        monkeypatch.setattr(mod, "_archive_task", lambda t, a: called.append(True) or True)
        reply = self._make_reply(tmp_path, APPROVE_REPLY)
        result = self._make_result(tmp_path)
        apply_review(reply, result, dry_run=False, auto_approve=False, auto_archive=True)
        assert not called

    def test_auto_archive_skipped_on_dry_run(self, tmp_path, monkeypatch):
        """dry_run=True のとき _archive_task は呼ばれない。"""
        monkeypatch.setattr(mod, "_run_cycle_approve", lambda: True)
        called = []
        monkeypatch.setattr(mod, "_archive_task", lambda t, a: called.append(True) or True)
        reply = self._make_reply(tmp_path, APPROVE_REPLY)
        result = self._make_result(tmp_path)
        apply_review(reply, result, dry_run=True, auto_approve=True, auto_archive=True)
        assert not called

    def test_auto_archive_skipped_on_request_changes(self, tmp_path, monkeypatch):
        """decision=request_changes のとき _archive_task は呼ばれない。"""
        called = []
        monkeypatch.setattr(mod, "_archive_task", lambda t, a: called.append(True) or True)
        reply = self._make_reply(tmp_path, REQUEST_REPLY)
        result = self._make_result(tmp_path)
        apply_review(reply, result, dry_run=False, auto_approve=True, auto_archive=True)
        assert not called

    def test_auto_reject_calls_cycle_reject_on_request_changes(self, tmp_path, monkeypatch):
        """auto_reject=True + request_changes → _run_cycle_reject が呼ばれる。"""
        called = []
        monkeypatch.setattr(mod, "_run_cycle_reject", lambda r: called.append(r) or True)
        reply = self._make_reply(tmp_path, REQUEST_REPLY)
        result = self._make_result(tmp_path)
        rc = apply_review(reply, result, dry_run=False, auto_reject=True)
        assert rc == 0
        assert called
        assert called[0] == "foo.py にテストを追加する"

    def test_auto_reject_skipped_on_approve(self, tmp_path, monkeypatch):
        """auto_reject=True でも approve のとき _run_cycle_reject は呼ばれない。"""
        called = []
        monkeypatch.setattr(mod, "_run_cycle_reject", lambda r: called.append(r) or True)
        reply = self._make_reply(tmp_path, APPROVE_REPLY)
        result = self._make_result(tmp_path)
        apply_review(reply, result, dry_run=False, auto_reject=True)
        assert not called

    def test_auto_reject_failure_returns_zero(self, tmp_path, monkeypatch):
        """_run_cycle_reject 失敗時も rc=0 で返る（fail-open）。"""
        monkeypatch.setattr(mod, "_run_cycle_reject", lambda r: False)
        reply = self._make_reply(tmp_path, REQUEST_REPLY)
        result = self._make_result(tmp_path)
        rc = apply_review(reply, result, dry_run=False, auto_reject=True)
        assert rc == 0

    def test_auto_reject_skipped_on_dry_run(self, tmp_path, monkeypatch):
        """dry_run=True のとき _run_cycle_reject は呼ばれない。"""
        called = []
        monkeypatch.setattr(mod, "_run_cycle_reject", lambda r: called.append(r) or True)
        reply = self._make_reply(tmp_path, REQUEST_REPLY)
        result = self._make_result(tmp_path)
        apply_review(reply, result, dry_run=True, auto_reject=True)
        assert not called


class TestEndToEnd:
    """apply_review の全ステップを実ファイルで通す統合テスト。"""

    def _make_reply(self, tmp_path: Path, content: str) -> Path:
        p = tmp_path / "review_reply.md"
        p.write_text(content, encoding="utf-8")
        return p

    def _make_result(self, tmp_path: Path) -> Path:
        p = tmp_path / "result.md"
        p.write_text("---\nstatus: review-pending\n---\n", encoding="utf-8")
        return p

    def _make_task(self, tmp_path: Path) -> Path:
        p = tmp_path / "task.md"
        p.write_text(
            '---\ntask_id: "0099"\nslug: "e2e-test"\nstatus: approved\nupdated: 2026-04-03\n---\n',
            encoding="utf-8",
        )
        return p

    def test_full_approve_flow(self, tmp_path, monkeypatch):
        """approve → result.md 更新 → cycle_approve 成功 → task.md archive 移動。"""
        monkeypatch.setattr(mod, "_run_cycle_approve", lambda: True)
        monkeypatch.setattr(mod, "TASK_MD", tmp_path / "task.md")
        monkeypatch.setattr(mod, "ARCHIVE_DIR", tmp_path / "archive")
        reply = self._make_reply(tmp_path, APPROVE_REPLY)
        result = self._make_result(tmp_path)
        task = self._make_task(tmp_path)

        rc = apply_review(reply, result, dry_run=False, auto_approve=True, auto_archive=True)

        assert rc == 0
        assert "status: reviewed" in result.read_text(encoding="utf-8")
        dest = tmp_path / "archive" / "20260403_task_0099_e2e-test.md"
        assert dest.exists()
        assert "status: done" in dest.read_text(encoding="utf-8")
        assert not task.exists()

    def test_approve_failure_leaves_task_md(self, tmp_path, monkeypatch):
        """cycle_approve 失敗時は result.md 更新済み・task.md 未移動。"""
        monkeypatch.setattr(mod, "_run_cycle_approve", lambda: False)
        monkeypatch.setattr(mod, "TASK_MD", tmp_path / "task.md")
        monkeypatch.setattr(mod, "ARCHIVE_DIR", tmp_path / "archive")
        reply = self._make_reply(tmp_path, APPROVE_REPLY)
        result = self._make_result(tmp_path)
        task = self._make_task(tmp_path)

        rc = apply_review(reply, result, dry_run=False, auto_approve=True, auto_archive=True)

        assert rc == 0
        assert "status: reviewed" in result.read_text(encoding="utf-8")
        assert task.exists()
        assert not (tmp_path / "archive").exists()


class TestArchiveTask:

    def _make_task(self, tmp_path: Path, task_id: str = "0042", slug: str = "my-task",
                   updated: str = "2026-04-03", status: str = "approved") -> Path:
        p = tmp_path / "task.md"
        p.write_text(
            f'---\ntask_id: "{task_id}"\nslug: "{slug}"\nstatus: {status}\nupdated: {updated}\n---\n',
            encoding="utf-8",
        )
        return p

    def test_moves_to_archive(self, tmp_path):
        task = self._make_task(tmp_path)
        archive = tmp_path / "archive"
        assert _archive_task(task, archive)
        dest = archive / "20260403_task_0042_my-task.md"
        assert dest.exists()
        assert not task.exists()

    def test_status_updated_to_done(self, tmp_path):
        task = self._make_task(tmp_path)
        archive = tmp_path / "archive"
        _archive_task(task, archive)
        dest = archive / "20260403_task_0042_my-task.md"
        assert "status: done" in dest.read_text(encoding="utf-8")

    def test_aborts_on_empty_task_id(self, tmp_path):
        task = self._make_task(tmp_path, task_id="")
        archive = tmp_path / "archive"
        assert not _archive_task(task, archive)
        assert task.exists()

    def test_aborts_on_duplicate_dest(self, tmp_path):
        task = self._make_task(tmp_path)
        archive = tmp_path / "archive"
        archive.mkdir()
        (archive / "20260403_task_0042_my-task.md").write_text("existing", encoding="utf-8")
        assert not _archive_task(task, archive)
        assert task.exists()

    def test_aborts_on_missing_task_md(self, tmp_path):
        assert not _archive_task(tmp_path / "nonexistent.md", tmp_path / "archive")
