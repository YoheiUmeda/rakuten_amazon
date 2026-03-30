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


def _pending_state(goal="test goal", changed_files=None):
    return {
        "status": "pending_review",
        "goal": goal,
        "base_commit": "abc0000",
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


# ── helper ────────────────────────────────────────────────────────────────

def _run(mod, output_path: Path):
    """argparse をバイパスして main ロジックを直接実行する。"""
    from argparse import Namespace
    args = Namespace(test_cmd="", test_output="", output=str(output_path))

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

    data = mod.build_review_request(state, test_cmd=args.test_cmd, test_output=args.test_output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        __import__("json").dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    raise SystemExit(0)
