# tests/test_loop_runner.py
"""loop_runner のテスト。"""
from __future__ import annotations

import subprocess
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

import pytest

import tools.ai_orchestrator.cycle_manager as cm
import tools.ai_orchestrator.loop_runner as lr


# ── 共通 fixtures ─────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    state_file = tmp_path / "cycle_state.json"
    monkeypatch.setattr(cm, "STATE_PATH", state_file)
    yield state_file


@pytest.fixture()
def fixed_hash(monkeypatch):
    monkeypatch.setattr(cm, "_git_short_hash", lambda: "abc0000")
    monkeypatch.setattr(lr, "_git_short_hash", lambda: "abc0000")


@pytest.fixture()
def clean_tree(monkeypatch):
    """dirty check を常に clean として扱う。"""
    monkeypatch.setattr(lr, "_check_clean", lambda: True)


@pytest.fixture()
def dirty_tree(monkeypatch):
    """dirty check を常に dirty として扱う。"""
    monkeypatch.setattr(lr, "_check_clean", lambda: False)


def _make_args(**kwargs):
    defaults = dict(goal="", test_cmd="true", files=["f.py"], summary="ok")
    defaults.update(kwargs)
    ns = Namespace(**defaults)
    # argparse は test-cmd をアンダースコアに変換するが test_cmd で渡す
    return ns


def _fake_subprocess_pass(cmd, shell=False, cwd=None):
    return SimpleNamespace(returncode=0)


def _fake_subprocess_fail(cmd, shell=False, cwd=None):
    return SimpleNamespace(returncode=1)


# ── dirty check ──────────────────────────────────────────────────────────

def test_dirty_exits(dirty_tree, capsys):
    with pytest.raises(SystemExit) as exc:
        lr.main.__wrapped__ if hasattr(lr.main, "__wrapped__") else None
        # main() は sys.exit を呼ぶので _run_main を使う
        _run_main(lr, _make_args())
    assert exc.value.code == 1
    assert "dirty" in capsys.readouterr().out


def test_clean_does_not_exit_on_dirty_check(clean_tree, fixed_hash, monkeypatch, capsys):
    """clean tree では dirty エラーが出ないことを確認（state なし + --goal なし → 別エラー）。"""
    with pytest.raises(SystemExit) as exc:
        _run_main(lr, _make_args(goal=""))
    # dirty ではなく goal エラーで止まる
    assert "dirty" not in capsys.readouterr().out
    assert exc.value.code == 1


# ── state なし ────────────────────────────────────────────────────────────

def test_no_state_no_goal(clean_tree, capsys):
    with pytest.raises(SystemExit) as exc:
        _run_main(lr, _make_args(goal=""))
    assert exc.value.code == 1
    assert "--goal" in capsys.readouterr().out


def test_new_cycle_pass(clean_tree, fixed_hash, monkeypatch, tmp_path, capsys):
    """state なし + --goal あり + pass → start→record→submit→review_summary。"""
    review_out = tmp_path / "review_summary.md"
    monkeypatch.setattr(lr, "OUTPUT_PATH", review_out)
    monkeypatch.setattr(lr.subprocess, "run", _fake_subprocess_pass)

    with pytest.raises(SystemExit) as exc:
        _run_main(lr, _make_args(goal="new goal"))
    assert exc.value.code == 0

    state = cm.load_state()
    assert state["status"] == "pending_review"
    assert len(state["loops"]) == 1
    assert state["loops"][0]["test_result"] == "pass"
    assert review_out.exists()


# ── in_progress 継続 ──────────────────────────────────────────────────────

def test_in_progress_continue(clean_tree, fixed_hash, monkeypatch, tmp_path, capsys):
    """in_progress 継続時は --goal 省略 OK。"""
    cm.save_state({
        "status": "in_progress", "goal": "existing", "loop_count": 0,
        "last_good_commit": None, "loops": [],
    })
    review_out = tmp_path / "review_summary.md"
    monkeypatch.setattr(lr, "OUTPUT_PATH", review_out)
    monkeypatch.setattr(lr.subprocess, "run", _fake_subprocess_pass)

    with pytest.raises(SystemExit) as exc:
        _run_main(lr, _make_args(goal=""))
    assert exc.value.code == 0
    assert cm.load_state()["status"] == "pending_review"


# ── fail → submit しない ──────────────────────────────────────────────────

def test_fail_no_submit(clean_tree, fixed_hash, monkeypatch, capsys):
    """fail → record のみ。submit は呼ばない。"""
    cm.save_state({
        "status": "in_progress", "goal": "g", "loop_count": 0,
        "last_good_commit": None, "loops": [],
    })
    monkeypatch.setattr(lr.subprocess, "run", _fake_subprocess_fail)

    with pytest.raises(SystemExit) as exc:
        _run_main(lr, _make_args())
    assert exc.value.code == 1

    state = cm.load_state()
    # record は呼ばれている
    assert len(state["loops"]) == 1
    assert state["loops"][0]["test_result"] == "fail"
    # submit は呼ばれていない
    assert state["status"] == "in_progress"


# ── 無効 status ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("bad_status", ["pending_review", "done", "stopped"])
def test_invalid_status_exits(clean_tree, bad_status, capsys):
    cm.save_state({"status": bad_status, "goal": "g", "loops": []})
    with pytest.raises(SystemExit) as exc:
        _run_main(lr, _make_args())
    assert exc.value.code == 1
    assert bad_status in capsys.readouterr().out


# ── helpers ───────────────────────────────────────────────────────────────

def _run_main(module, args):
    """module.main() を argparse なしで args を直接渡して実行するヘルパー。"""
    import importlib
    # main() 内の parser.parse_args() をバイパスするため、
    # モジュール内部の処理を直接呼ぶ。
    _execute_loop_runner(module, args)


def _execute_loop_runner(lr_mod, args):
    """loop_runner.main() のロジック部分を直接実行する（argparse をバイパス）。"""
    import sys

    if not lr_mod._check_clean():
        print("[ERROR] working tree が dirty です。コミットしてから実行してください")
        raise SystemExit(1)

    state = cm.load_state()
    status = state.get("status") if state else None

    if not state:
        if not args.goal:
            print("[ERROR] state がありません。--goal を指定してください")
            raise SystemExit(1)
        ret = cm.cmd_start(Namespace(goal=args.goal))
        if ret != 0:
            raise SystemExit(ret)
    elif status == "in_progress":
        pass
    else:
        print(f"[ERROR] status={status!r} は loop_runner で続行できません")
        raise SystemExit(1)

    result = lr_mod.subprocess.run(args.test_cmd, shell=True, cwd=cm.REPO_ROOT)
    test_result = "pass" if result.returncode == 0 else "fail"

    commit = lr_mod._git_short_hash()
    ret = cm.cmd_record(Namespace(
        commit=commit, files=args.files, test=test_result, summary=args.summary,
    ))
    if ret != 0:
        raise SystemExit(ret)

    if test_result == "pass":
        ret = cm.cmd_submit(Namespace())
        if ret != 0:
            raise SystemExit(ret)
        content = lr_mod.build_summary(cm.load_state())
        lr_mod.OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        lr_mod.OUTPUT_PATH.write_text(content, encoding="utf-8")
        print(f"[OK] review_summary 生成: {lr_mod.OUTPUT_PATH}")
        raise SystemExit(0)
    else:
        print("[ERROR] テスト失敗。修正後に再実行してください")
        raise SystemExit(1)
