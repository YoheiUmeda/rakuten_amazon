# tests/test_cycle_to_review_request.py
"""cycle_to_review_request の最小テスト。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import tools.ai_orchestrator.cycle_manager as cm
import tools.ai_orchestrator.cycle_to_review_request as ctr


# ── fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    state_file = tmp_path / "cycle_state.json"
    monkeypatch.setattr(cm, "STATE_PATH", state_file)
    yield state_file


@pytest.fixture()
def no_git_diff(monkeypatch):
    monkeypatch.setattr(ctr, "_git_diff", lambda base: "")


def _pending_state(goal="test goal", changed_files=None, ng_history=None):
    return {
        "status": "pending_review",
        "goal": goal,
        "base_commit": "abc0000",
        "ng_history": ng_history if ng_history is not None else [],
        "loops": [
            {
                "loop_id": 1,
                "changed_files": changed_files if changed_files is not None else ["src/foo.py"],
                "test_result": "pass",
            }
        ],
    }


# ── 正常系 ────────────────────────────────────────────────────────────────

def test_normal(isolated_state, no_git_diff, tmp_path):
    cm.save_state(_pending_state())
    out = tmp_path / "review_request.json"

    with pytest.raises(SystemExit) as exc:
        _run(ctr, out)
    assert exc.value.code == 0

    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["task"] == "test goal"
    assert data["changed_files"] == ["src/foo.py"]
    assert "git_diff" in data


def test_normal_deduplicates_files(isolated_state, no_git_diff, tmp_path):
    """複数ループで同一ファイルが重複しない。"""
    state = _pending_state()
    state["loops"].append({
        "loop_id": 2,
        "changed_files": ["src/foo.py", "src/bar.py"],
        "test_result": "pass",
    })
    cm.save_state(state)
    out = tmp_path / "review_request.json"

    with pytest.raises(SystemExit) as exc:
        _run(ctr, out)
    assert exc.value.code == 0

    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["changed_files"] == ["src/foo.py", "src/bar.py"]


# ── state 不在 ────────────────────────────────────────────────────────────

def test_no_state(isolated_state, tmp_path, capsys):
    out = tmp_path / "review_request.json"
    with pytest.raises(SystemExit) as exc:
        _run(ctr, out)
    assert exc.value.code == 1
    assert "cycle_state.json" in capsys.readouterr().out


# ── pending_review 以外は exit 1 ──────────────────────────────────────────

@pytest.mark.parametrize("bad_status", ["in_progress", "done", "stopped"])
def test_wrong_status(isolated_state, bad_status, tmp_path, capsys):
    cm.save_state({
        "status": bad_status, "goal": "g",
        "loops": [{"loop_id": 1, "changed_files": ["f.py"], "test_result": "pass"}],
    })
    out = tmp_path / "review_request.json"
    with pytest.raises(SystemExit) as exc:
        _run(ctr, out)
    assert exc.value.code == 1
    assert bad_status in capsys.readouterr().out


# ── changed_files 空 → exit 1 ─────────────────────────────────────────────

def test_empty_changed_files(isolated_state, tmp_path, capsys):
    cm.save_state(_pending_state(changed_files=[]))
    out = tmp_path / "review_request.json"
    with pytest.raises(SystemExit) as exc:
        _run(ctr, out)
    assert exc.value.code == 1
    assert "changed_files" in capsys.readouterr().out


# ── task 空 → exit 1 ──────────────────────────────────────────────────────

def test_empty_task(isolated_state, tmp_path, capsys):
    cm.save_state(_pending_state(goal=""))
    out = tmp_path / "review_request.json"
    with pytest.raises(SystemExit) as exc:
        _run(ctr, out)
    assert exc.value.code == 1
    assert "goal" in capsys.readouterr().out


# ── enrichment tests ─────────────────────────────────────────────────────

def test_constraints_from_task_md(tmp_path, no_git_diff):
    """task.md の実施条件・制約が constraints フィールドに入ること。"""
    task_md = tmp_path / "task.md"
    task_md.write_text(
        "## タスク\nfoo\n\n## 実施条件・制約\n- 制約A\n- 制約B\n\n## 背景\nbar\n",
        encoding="utf-8",
    )
    state = _pending_state()
    data = ctr.build_review_request(state, task_md_path=task_md)
    assert data.get("constraints") == ["制約A", "制約B"]


def test_constraints_absent_when_task_md_missing(tmp_path, no_git_diff):
    """task.md が存在しない場合 constraints フィールドが出力されないこと。"""
    state = _pending_state()
    data = ctr.build_review_request(state, task_md_path=tmp_path / "nonexistent.md")
    assert "constraints" not in data


def test_constraints_absent_when_section_empty(tmp_path, no_git_diff):
    """実施条件・制約セクションが空(箇条書きなし)のとき constraints が出力されないこと。"""
    task_md = tmp_path / "task.md"
    task_md.write_text("## 実施条件・制約\n-\n\n## 背景\nbar\n", encoding="utf-8")
    state = _pending_state()
    data = ctr.build_review_request(state, task_md_path=task_md)
    assert "constraints" not in data


def test_open_questions_from_ng_history(tmp_path, no_git_diff):
    """ng_history の reason が open_questions に入ること。"""
    state = _pending_state(ng_history=[
        {"timestamp": "2026-01-01T00:00:00+09:00", "reason": "テスト失敗: foo"},
        {"timestamp": "2026-01-02T00:00:00+09:00", "reason": "スコープ外変更"},
    ])
    data = ctr.build_review_request(state, task_md_path=tmp_path / "no.md")
    assert data.get("open_questions") == ["テスト失敗: foo", "スコープ外変更"]


def test_open_questions_absent_when_ng_history_empty(tmp_path, no_git_diff):
    """ng_history が空のとき open_questions フィールドが出力されないこと。"""
    state = _pending_state()
    data = ctr.build_review_request(state, task_md_path=tmp_path / "no.md")
    assert "open_questions" not in data


def test_summary_from_review_summary_md(tmp_path, no_git_diff):
    """review_summary.md の懸念点セクションが summary フィールドに入ること。"""
    summary_md = tmp_path / "review_summary.md"
    summary_md.write_text(
        "## 懸念点\n- テスト網羅率が低い\n- 副作用未確認\n\n## 次の判断\nOK\n",
        encoding="utf-8",
    )
    state = _pending_state()
    data = ctr.build_review_request(state, review_summary_path=summary_md)
    assert "テスト網羅率が低い" in data.get("summary", "")


def test_summary_absent_when_nashi(tmp_path, no_git_diff):
    """懸念点が「- なし」のとき summary フィールドが出力されないこと。"""
    summary_md = tmp_path / "review_summary.md"
    summary_md.write_text("## 懸念点\n- なし\n\n## 次の判断\nOK\n", encoding="utf-8")
    state = _pending_state()
    data = ctr.build_review_request(state, review_summary_path=summary_md)
    assert "summary" not in data


def test_summary_absent_when_file_missing(tmp_path, no_git_diff):
    """review_summary.md が存在しない場合 summary フィールドが出力されないこと。"""
    state = _pending_state()
    data = ctr.build_review_request(state, review_summary_path=tmp_path / "no.md")
    assert "summary" not in data


def test_test_log_path_included(tmp_path, no_git_diff):
    """test_log_path が指定された場合、review_request に含まれること。"""
    state = _pending_state()
    data = ctr.build_review_request(state, test_log_path=".ai/logs/test_abc0000_pass_20260403.log")
    assert data.get("test_log_path") == ".ai/logs/test_abc0000_pass_20260403.log"


def test_test_log_path_absent_when_empty(tmp_path, no_git_diff):
    """test_log_path が空なら review_request に含まれないこと。"""
    state = _pending_state()
    data = ctr.build_review_request(state)
    assert "test_log_path" not in data


# ── review_mode / metadata ────────────────────────────────────────────────

def test_review_mode_verification_by_keyword(no_git_diff):
    """goal に verification キーワードが含まれる場合、review_mode = 'verification'。"""
    state = _pending_state(goal="review_request metadata for false positive reduction")
    data = ctr.build_review_request(state)
    assert data["review_mode"] == "verification"
    assert "automation_path" in data


def test_review_mode_verification_by_files(no_git_diff):
    """全 changed_files が orchestrator/tests 配下なら review_mode = 'verification'。"""
    state = _pending_state(goal="fix something", changed_files=["tools/ai_orchestrator/foo.py"])
    data = ctr.build_review_request(state)
    assert data["review_mode"] == "verification"


def test_review_mode_production(no_git_diff):
    """通常の業務ファイル変更は review_mode = 'production'、expected_non_blockers なし。"""
    state = _pending_state(goal="update price calculation", changed_files=["price_calculation.py"])
    data = ctr.build_review_request(state)
    assert data["review_mode"] == "production"
    assert "expected_non_blockers" not in data
    assert "automation_path" not in data


def test_expected_non_blockers_apply_review_file(no_git_diff):
    """apply_review.py が changed_files にある場合、apply 関連の非ブロッカーが追加される。"""
    state = _pending_state(goal="add flag", changed_files=["tools/ai_orchestrator/apply_review.py"])
    data = ctr.build_review_request(state)
    nb = data.get("expected_non_blockers", [])
    assert "result_status_missing_ok" in nb
    assert "task_archive_skip_ok" in nb


def test_expected_non_blockers_standalone_arg_file(no_git_diff):
    """review_summary.py が changed_files にある場合、standalone_optional_arg_path が追加される。"""
    state = _pending_state(goal="update output", changed_files=["tools/ai_orchestrator/review_summary.py"])
    data = ctr.build_review_request(state)
    assert "standalone_optional_arg_path" in data.get("expected_non_blockers", [])


def test_expected_non_blockers_absent_when_not_matched(no_git_diff):
    """cycle_to_review_request.py のみの変更では expected_non_blockers は省略される。"""
    state = _pending_state(goal="refactor metadata generation",
                           changed_files=["tools/ai_orchestrator/cycle_to_review_request.py"])
    data = ctr.build_review_request(state)
    assert data["review_mode"] == "verification"
    assert "expected_non_blockers" not in data


# ── _git_diff ────────────────────────────────────────────────────────────

class TestGitDiff:
    """_git_diff の fallback ロジックをテストする。"""

    def _make_fake_run(self, first_stdout: str, second_stdout: str = "", second_rc: int = 0):
        """1回目・2回目の subprocess.run 結果を制御するフェイク。"""
        from types import SimpleNamespace
        calls: list[list[str]] = []

        def fake_run(cmd, **kwargs):
            calls.append(list(cmd))
            if len(calls) == 1:
                return SimpleNamespace(returncode=0, stdout=first_stdout)
            return SimpleNamespace(returncode=second_rc, stdout=second_stdout)

        return fake_run, calls

    def test_primary_nonempty_returned_directly(self, monkeypatch):
        """base_commit..HEAD が非空のとき、そのまま返す（fallback は呼ばない）。"""
        fake_run, calls = self._make_fake_run(first_stdout="diff output")
        monkeypatch.setattr(ctr.subprocess, "run", fake_run)
        result = ctr._git_diff("abc0000")
        assert result == "diff output"
        assert len(calls) == 1

    def test_primary_empty_fallback_returned(self, monkeypatch):
        """base_commit..HEAD が空のとき、fallback base_commit^..base_commit を返す。"""
        fake_run, calls = self._make_fake_run(first_stdout="", second_stdout="fallback diff")
        monkeypatch.setattr(ctr.subprocess, "run", fake_run)
        result = ctr._git_diff("abc0000")
        assert result == "fallback diff"
        assert len(calls) == 2

    def test_empty_base_commit_returns_empty(self, monkeypatch):
        """base_commit が空文字のとき、subprocess を呼ばずに空文字を返す。"""
        fake_run, calls = self._make_fake_run(first_stdout="should not be called")
        monkeypatch.setattr(ctr.subprocess, "run", fake_run)
        result = ctr._git_diff("")
        assert result == ""
        assert len(calls) == 0

    def test_fallback_fails_returns_empty(self, monkeypatch):
        """fallback 実行時に returncode != 0 のとき、空文字を返す。"""
        fake_run, calls = self._make_fake_run(first_stdout="", second_stdout="", second_rc=1)
        monkeypatch.setattr(ctr.subprocess, "run", fake_run)
        result = ctr._git_diff("abc0000")
        assert result == ""
        assert len(calls) == 2


# ── helper ────────────────────────────────────────────────────────────────

def _run(mod, output_path: Path, task_md_path: Path | None = None, review_summary_path: Path | None = None):
    """argparse をバイパスして main ロジックを直接実行する。"""
    from argparse import Namespace
    args = Namespace(test_cmd="", test_output="", test_log_path="", output=str(output_path))

    state = cm.load_state()
    if not state:
        print("[ERROR] cycle_state.json が見つかりません。先に cycle_manager start を実行してください")
        raise SystemExit(1)

    status = state.get("status")
    if status != "pending_review":
        print(f"[ERROR] status={status!r} です。review_request.json を生成できるのは pending_review のときだけです")
        raise SystemExit(1)

    task = state.get("goal", "")
    if not task:
        print("[ERROR] goal が空です。review_request.json を生成できません")
        raise SystemExit(1)

    loops = state.get("loops", [])
    seen: set[str] = set()
    changed_files: list[str] = []
    for lp in loops:
        for f in lp.get("changed_files", []):
            if f not in seen:
                changed_files.append(f)
                seen.add(f)

    if not changed_files:
        print("[ERROR] 全ループを通じて changed_files が空です。review_request.json を生成できません")
        raise SystemExit(1)

    data = mod.build_review_request(
        state,
        test_cmd=args.test_cmd,
        test_output=args.test_output,
        test_log_path=args.test_log_path,
        task_md_path=task_md_path,
        review_summary_path=review_summary_path,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        __import__("json").dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    raise SystemExit(0)
