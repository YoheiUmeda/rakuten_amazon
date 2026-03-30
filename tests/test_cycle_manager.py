# tests/test_cycle_manager.py
"""cycle_manager の最小テスト。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

import tools.ai_orchestrator.cycle_manager as cm


def _make_args(**kwargs) -> argparse.Namespace:
    defaults = dict(goal="", commit="", files=[], test="pass", summary="", reason="")
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def _load(state_path: Path) -> dict:
    return json.loads(state_path.read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    """STATE_PATH を tmp_path 以下に差し替えてテスト間を分離する。"""
    state_file = tmp_path / "cycle_state.json"
    monkeypatch.setattr(cm, "STATE_PATH", state_file)
    yield state_file


@pytest.fixture()
def fixed_hash(monkeypatch):
    monkeypatch.setattr(cm, "_git_short_hash", lambda: "abc0000")


# ── start ────────────────────────────────────────────────────────────────

def test_start_creates_state(isolated_state, fixed_hash):
    ret = cm.cmd_start(_make_args(goal="test goal"))
    assert ret == 0
    state = _load(isolated_state)
    assert state["goal"] == "test goal"
    assert state["status"] == "in_progress"
    assert state["base_commit"] == "abc0000"
    assert state["loops"] == []


@pytest.mark.parametrize("active_status", ["in_progress", "pending_review"])
def test_start_guard_active_cycle(isolated_state, active_status):
    # 既存サイクルを直接書き込む
    cm.save_state({"status": active_status, "goal": "existing", "loops": []})
    ret = cm.cmd_start(_make_args(goal="new"))
    assert ret == 1


# ── record ───────────────────────────────────────────────────────────────

def test_record_appends_loop(isolated_state, fixed_hash):
    cm.save_state({
        "status": "in_progress", "goal": "g", "loop_count": 0,
        "last_good_commit": None, "loops": [],
    })
    ret = cm.cmd_record(_make_args(commit="c1", files=["f.py"], test="pass", summary="ok"))
    assert ret == 0
    state = _load(isolated_state)
    assert state["loop_count"] == 1
    assert len(state["loops"]) == 1
    assert state["loops"][0]["commit"] == "c1"


def test_record_last_good_commit_pass(isolated_state, fixed_hash):
    cm.save_state({
        "status": "in_progress", "goal": "g", "loop_count": 0,
        "last_good_commit": None, "loops": [],
    })
    cm.cmd_record(_make_args(commit="good1", test="pass"))
    state = _load(isolated_state)
    assert state["last_good_commit"] == "good1"


def test_record_last_good_commit_fail(isolated_state, fixed_hash):
    cm.save_state({
        "status": "in_progress", "goal": "g", "loop_count": 0,
        "last_good_commit": None, "loops": [],
    })
    cm.cmd_record(_make_args(commit="bad1", test="fail"))
    state = _load(isolated_state)
    assert state["last_good_commit"] is None


# ── submit ────────────────────────────────────────────────────────────────

def test_submit_ok(isolated_state):
    cm.save_state({
        "status": "in_progress", "goal": "g",
        "loops": [{"loop_id": 1}],
    })
    ret = cm.cmd_submit(_make_args())
    assert ret == 0
    assert _load(isolated_state)["status"] == "pending_review"


def test_submit_no_loops(isolated_state):
    cm.save_state({"status": "in_progress", "goal": "g", "loops": []})
    ret = cm.cmd_submit(_make_args())
    assert ret == 1


# ── approve ───────────────────────────────────────────────────────────────

def test_approve_ok(isolated_state):
    cm.save_state({"status": "pending_review", "goal": "g", "loops": []})
    ret = cm.cmd_approve(_make_args())
    assert ret == 0
    assert _load(isolated_state)["status"] == "done"


def test_approve_wrong_status(isolated_state):
    cm.save_state({"status": "in_progress", "goal": "g", "loops": []})
    ret = cm.cmd_approve(_make_args())
    assert ret == 1


# ── reject ────────────────────────────────────────────────────────────────

def test_reject_ok(isolated_state):
    cm.save_state({
        "status": "pending_review", "goal": "g",
        "loops": [], "ng_history": [],
    })
    ret = cm.cmd_reject(_make_args(reason="fix this"))
    assert ret == 0
    state = _load(isolated_state)
    assert state["status"] == "in_progress"
    assert state["last_reject_reason"] == "fix this"
    assert len(state["ng_history"]) == 1
    assert state["ng_history"][0]["reason"] == "fix this"


def test_reject_no_reason(isolated_state):
    cm.save_state({"status": "pending_review", "goal": "g", "loops": []})
    ret = cm.cmd_reject(_make_args(reason=""))
    assert ret == 1


# ── status: latest loop ───────────────────────────────────────────────────

def test_status_latest_loop(isolated_state, capsys):
    cm.save_state({
        "status": "in_progress", "goal": "g", "loop_count": 1,
        "base_commit": "abc", "last_good_commit": None,
        "loops": [{
            "loop_id": 1, "timestamp": "2026-01-01T00:00:00+09:00",
            "pre_commit": "aaa", "commit": "bbb",
            "changed_files": ["foo.py", "bar.py"],
            "test_result": "pass", "summary": "修正完了",
        }],
    })
    ret = cm.cmd_status(_make_args())
    assert ret == 0
    out = capsys.readouterr().out
    assert "latest loop:" in out
    assert "修正完了" in out
    assert "pass" in out
    assert "foo.py" in out


def test_status_no_loops(isolated_state, capsys):
    cm.save_state({
        "status": "in_progress", "goal": "g", "loop_count": 0,
        "base_commit": "abc", "last_good_commit": None, "loops": [],
    })
    ret = cm.cmd_status(_make_args())
    assert ret == 0
    out = capsys.readouterr().out
    assert "latest loop:" not in out


# ── stop ─────────────────────────────────────────────────────────────────

def test_stop_ok(isolated_state):
    cm.save_state({"status": "in_progress", "goal": "g", "loops": []})
    ret = cm.cmd_stop(_make_args(reason="manual"))
    assert ret == 0
    state = _load(isolated_state)
    assert state["status"] == "stopped"
    assert state["stop_reason"] == "manual"
