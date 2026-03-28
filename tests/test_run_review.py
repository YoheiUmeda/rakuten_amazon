# tests/test_run_review.py
"""
run_review wrapper のテスト。
openai / OPENAI_API_KEY 不要。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT   = Path(__file__).resolve().parents[1]
VENV_PYTHON = REPO_ROOT / "venv" / "Scripts" / "python.exe"


def _py() -> str:
    return str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable


def _args(**kwargs) -> argparse.Namespace:
    """テスト用 Namespace を生成するヘルパー。"""
    defaults = dict(
        task="テスト", staged=False, files=[], test_cmd="",
        run_tests=False, related_code=[], open_questions=[],
        constraints=[], dry_run=False, save_only=False, model=None,
    )
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


# ──────────────────────────────────────────────────────────────────────────
# subprocess CLI テスト
# ──────────────────────────────────────────────────────────────────────────

class TestRunReviewCLI:

    def test_dry_run_exits_zero(self):
        """--dry-run が exit 0 で終わること。"""
        r = subprocess.run(
            [_py(), "-m", "tools.ai_orchestrator.run_review",
             "--task", "テスト", "--staged", "--dry-run"],
            capture_output=True, text=True, encoding="utf-8", cwd=REPO_ROOT,
        )
        assert r.returncode == 0, f"stderr: {r.stderr}"


# ──────────────────────────────────────────────────────────────────────────
# fail-open 経路テスト（monkeypatch）
# ──────────────────────────────────────────────────────────────────────────

class TestFailOpen:

    def test_generate_nonzero_exit_is_failopen(self, monkeypatch):
        """generate が returncode=1 → run_review は sys.exit(0)（fail-open）。"""
        from tools.ai_orchestrator import run_review
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: subprocess.CompletedProcess([], returncode=1),
        )
        with pytest.raises(SystemExit) as exc:
            run_review.run(_args())
        assert exc.value.code == 0

    def test_orchestrator_nonzero_exit_is_failopen(self, monkeypatch):
        """orchestrator が returncode=1 → run_review は sys.exit(0)（fail-open）。"""
        from tools.ai_orchestrator import run_review
        call_count: dict[str, int] = {"n": 0}

        def fake_run(*a, **kw):
            call_count["n"] += 1
            # 1回目（generate）成功、2回目（orchestrator）失敗
            return subprocess.CompletedProcess([], returncode=0 if call_count["n"] == 1 else 1)

        monkeypatch.setattr(subprocess, "run", fake_run)
        with pytest.raises(SystemExit) as exc:
            run_review.run(_args())
        assert exc.value.code == 0

    def test_dry_run_skips_orchestrator(self, monkeypatch):
        """--dry-run のとき orchestrator が呼ばれないこと。"""
        from tools.ai_orchestrator import run_review
        call_count: dict[str, int] = {"n": 0}

        def fake_run(*a, **kw):
            call_count["n"] += 1
            return subprocess.CompletedProcess([], returncode=0)

        monkeypatch.setattr(subprocess, "run", fake_run)
        run_review.run(_args(dry_run=True))
        assert call_count["n"] == 1  # generate のみ、orchestrator は呼ばれない

    def test_generate_timeout_is_failopen(self, monkeypatch):
        """generate がタイムアウト → run_review は exit 0（fail-open）。"""
        from tools.ai_orchestrator import run_review

        def raise_timeout(*a, **kw):
            raise subprocess.TimeoutExpired("cmd", 300)

        monkeypatch.setattr(subprocess, "run", raise_timeout)
        with pytest.raises(SystemExit) as exc:
            run_review.run(_args())
        assert exc.value.code == 0

    def test_orchestrator_timeout_is_failopen(self, monkeypatch):
        """orchestrator がタイムアウト → run_review は exit 0（fail-open）。"""
        from tools.ai_orchestrator import run_review
        call_count: dict[str, int] = {"n": 0}

        def fake_run(*a, **kw):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return subprocess.CompletedProcess([], returncode=0)
            raise subprocess.TimeoutExpired("cmd", 300)

        monkeypatch.setattr(subprocess, "run", fake_run)
        with pytest.raises(SystemExit) as exc:
            run_review.run(_args())
        assert exc.value.code == 0


# ──────────────────────────────────────────────────────────────────────────
# --save-only テスト
# ──────────────────────────────────────────────────────────────────────────

class TestSaveOnly:

    def test_save_only_calls_generate_not_orchestrator(self, monkeypatch):
        """--save-only: generate は呼ばれ、orchestrator は呼ばれないこと。"""
        from tools.ai_orchestrator import run_review
        call_count: dict[str, int] = {"n": 0}

        def fake_run(*a, **kw):
            call_count["n"] += 1
            return subprocess.CompletedProcess([], returncode=0)

        monkeypatch.setattr(subprocess, "run", fake_run)
        run_review.run(_args(save_only=True))
        assert call_count["n"] == 1  # generate のみ

    def test_save_only_exits_zero_via_cli(self):
        """--save-only が exit 0 で終わること（CLI 経由）。"""
        r = subprocess.run(
            [_py(), "-m", "tools.ai_orchestrator.run_review",
             "--task", "テスト", "--staged", "--save-only"],
            capture_output=True, text=True, encoding="utf-8", cwd=REPO_ROOT,
        )
        assert r.returncode == 0, f"stderr: {r.stderr}"

    def test_save_only_does_not_pass_dry_run_to_generate(self, monkeypatch):
        """--save-only は generate に --dry-run を渡さない（JSON を実際に保存させる）。"""
        from tools.ai_orchestrator import run_review
        captured: list[list] = []

        def fake_run(cmd, **kw):
            captured.append(list(cmd))
            return subprocess.CompletedProcess(cmd, returncode=0)

        monkeypatch.setattr(subprocess, "run", fake_run)
        run_review.run(_args(save_only=True))
        assert captured, "generate が呼ばれていない"
        gen_cmd = captured[0]
        assert "--dry-run" not in gen_cmd


# ──────────────────────────────────────────────────────────────────────────
# _print_json_summary テスト
# ──────────────────────────────────────────────────────────────────────────

class TestPrintJsonSummary:

    def test_shows_task_and_file_count(self, tmp_path, capsys):
        """task と changed_files 件数が出力に含まれること。"""
        import json
        from tools.ai_orchestrator.run_review import _print_json_summary
        p = tmp_path / "req.json"
        p.write_text(json.dumps({
            "task": "テストタスク", "changed_files": ["a.py", "b.py"]
        }, ensure_ascii=False), encoding="utf-8")
        _print_json_summary(p)
        out = capsys.readouterr().out
        assert "テストタスク" in out
        assert "2" in out  # files count

    def test_missing_file_is_silently_skipped(self, tmp_path):
        """ファイル不在でも例外が出ないこと。"""
        from tools.ai_orchestrator.run_review import _print_json_summary
        _print_json_summary(tmp_path / "nonexistent.json")  # 例外なし

    def test_shows_test_output_preview(self, tmp_path, capsys):
        """test_output の先頭が表示されること。"""
        import json
        from tools.ai_orchestrator.run_review import _print_json_summary
        p = tmp_path / "req.json"
        p.write_text(json.dumps({
            "task": "t", "changed_files": [],
            "test_output": "5 passed in 1.23s"
        }), encoding="utf-8")
        _print_json_summary(p)
        out = capsys.readouterr().out
        assert "5 passed" in out

    def test_shows_model(self, tmp_path, capsys):
        """model フィールドが要約に表示されること。"""
        import json
        from tools.ai_orchestrator.run_review import _print_json_summary
        p = tmp_path / "req.json"
        p.write_text(json.dumps({
            "task": "t", "changed_files": [], "model": "gpt-4o-mini"
        }), encoding="utf-8")
        _print_json_summary(p)
        out = capsys.readouterr().out
        assert "gpt-4o-mini" in out


# ──────────────────────────────────────────────────────────────────────────
# --model パススルーテスト
# ──────────────────────────────────────────────────────────────────────────

class TestModelPassthrough:

    def test_model_arg_passed_to_generate(self, monkeypatch):
        """--model が generate コマンドに渡されること。"""
        from tools.ai_orchestrator import run_review
        captured: list[list] = []

        def fake_run(cmd, **kw):
            captured.append(list(cmd))
            return subprocess.CompletedProcess(cmd, returncode=0)

        monkeypatch.setattr(subprocess, "run", fake_run)
        run_review.run(_args(dry_run=True, model="gpt-4o"))
        assert captured, "generate が呼ばれていない"
        gen_cmd = captured[0]
        assert "--model" in gen_cmd
        idx = gen_cmd.index("--model")
        assert gen_cmd[idx + 1] == "gpt-4o"

    def test_no_model_arg_not_passed(self, monkeypatch):
        """--model 未指定のとき generate コマンドに --model が含まれないこと。"""
        from tools.ai_orchestrator import run_review
        captured: list[list] = []

        def fake_run(cmd, **kw):
            captured.append(list(cmd))
            return subprocess.CompletedProcess(cmd, returncode=0)

        monkeypatch.setattr(subprocess, "run", fake_run)
        run_review.run(_args(dry_run=True, model=None))
        gen_cmd = captured[0]
        assert "--model" not in gen_cmd


# ──────────────────────────────────────────────────────────────────────────
# run history テスト
# ──────────────────────────────────────────────────────────────────────────

class TestAppendHistory:

    def test_history_appended_on_dry_run(self, tmp_path, monkeypatch):
        """dry-run 完了時に履歴が JSONL に追記されること。"""
        import json as _json
        from tools.ai_orchestrator import run_review
        monkeypatch.setattr(run_review, "LOG_PATH", tmp_path / "runs.jsonl")

        def fake_run(*a, **kw):
            return subprocess.CompletedProcess([], returncode=0)
        monkeypatch.setattr(subprocess, "run", fake_run)
        run_review.run(_args(dry_run=True))

        lines = (tmp_path / "runs.jsonl").read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1
        e = _json.loads(lines[0])
        assert e["mode"] == "dry-run"
        assert e["success"] is True
        assert e["api_status"] == "skipped"

    def test_history_appended_on_save_only(self, tmp_path, monkeypatch):
        """save-only 完了時に履歴が残ること。"""
        import json as _json
        from tools.ai_orchestrator import run_review
        monkeypatch.setattr(run_review, "LOG_PATH", tmp_path / "runs.jsonl")

        def fake_run(*a, **kw):
            return subprocess.CompletedProcess([], returncode=0)
        monkeypatch.setattr(subprocess, "run", fake_run)
        run_review.run(_args(save_only=True))

        e = _json.loads((tmp_path / "runs.jsonl").read_text(encoding="utf-8"))
        assert e["mode"] == "save-only"
        assert e["success"] is True

    def test_history_on_generate_failure(self, tmp_path, monkeypatch):
        """generate 失敗時も履歴が残ること（success=False）。"""
        import json as _json
        from tools.ai_orchestrator import run_review
        monkeypatch.setattr(run_review, "LOG_PATH", tmp_path / "runs.jsonl")

        def fake_run(*a, **kw):
            return subprocess.CompletedProcess([], returncode=1)
        monkeypatch.setattr(subprocess, "run", fake_run)
        with pytest.raises(SystemExit):
            run_review.run(_args())

        e = _json.loads((tmp_path / "runs.jsonl").read_text(encoding="utf-8"))
        assert e["success"] is False

    def test_model_recorded_in_history(self, tmp_path, monkeypatch):
        """--model が履歴の model フィールドに記録されること。"""
        import json as _json
        from tools.ai_orchestrator import run_review
        monkeypatch.setattr(run_review, "LOG_PATH", tmp_path / "runs.jsonl")

        def fake_run(*a, **kw):
            return subprocess.CompletedProcess([], returncode=0)
        monkeypatch.setattr(subprocess, "run", fake_run)
        run_review.run(_args(dry_run=True, model="gpt-4o"))

        e = _json.loads((tmp_path / "runs.jsonl").read_text(encoding="utf-8"))
        assert e["model"] == "gpt-4o"

    def test_history_accumulates(self, tmp_path, monkeypatch):
        """複数回実行すると履歴が追記（上書きではなく）されること。"""
        import json as _json
        from tools.ai_orchestrator import run_review
        monkeypatch.setattr(run_review, "LOG_PATH", tmp_path / "runs.jsonl")

        def fake_run(*a, **kw):
            return subprocess.CompletedProcess([], returncode=0)
        monkeypatch.setattr(subprocess, "run", fake_run)
        run_review.run(_args(dry_run=True))
        run_review.run(_args(dry_run=True))

        lines = (tmp_path / "runs.jsonl").read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2

    def test_dry_run_with_files_has_correct_count(self, tmp_path, monkeypatch):
        """--files 指定の dry-run で changed_files_count が正しく記録されること。"""
        import json as _json
        from tools.ai_orchestrator import run_review
        monkeypatch.setattr(run_review, "LOG_PATH", tmp_path / "runs.jsonl")

        def fake_run(*a, **kw):
            return subprocess.CompletedProcess([], returncode=0)
        monkeypatch.setattr(subprocess, "run", fake_run)
        run_review.run(_args(dry_run=True, files=["a.py", "b.py", "c.py"]))

        e = _json.loads((tmp_path / "runs.jsonl").read_text(encoding="utf-8"))
        assert e["changed_files_count"] == 3

    def test_save_only_with_files_has_correct_count(self, tmp_path, monkeypatch):
        """--files 指定の save-only でも changed_files_count が正しく記録されること。"""
        import json as _json
        from tools.ai_orchestrator import run_review
        monkeypatch.setattr(run_review, "LOG_PATH", tmp_path / "runs.jsonl")

        def fake_run(*a, **kw):
            return subprocess.CompletedProcess([], returncode=0)
        monkeypatch.setattr(subprocess, "run", fake_run)
        run_review.run(_args(save_only=True, files=["x.py", "y.py"]))

        e = _json.loads((tmp_path / "runs.jsonl").read_text(encoding="utf-8"))
        assert e["changed_files_count"] == 2
