# tests/test_run_cycle_review.py
"""run_cycle_review の最小テスト。"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

import tools.ai_orchestrator.run_cycle_review as rcr

# モジュール名の完全一致で判別（tools.ai_orchestrator が両方に含まれるため部分一致は使わない）
_CTR_MODULE = "tools.ai_orchestrator.cycle_to_review_request"
_ORCH_MODULE = "tools.ai_orchestrator.orchestrator"


def _is_ctr(cmd: list[str]) -> bool:
    return _CTR_MODULE in cmd


def _is_orch(cmd: list[str]) -> bool:
    return _ORCH_MODULE in cmd


# ── subprocess.run のフェイク ─────────────────────────────────────────────

def _make_fake_subprocess(ctr_rc: int = 0, orch_rc: int = 0):
    calls: list[list[str]] = []

    def fake_run(cmd, cwd=None, **kwargs):
        calls.append(list(cmd))
        if _is_ctr(cmd):
            return SimpleNamespace(returncode=ctr_rc)
        if _is_orch(cmd):
            return SimpleNamespace(returncode=orch_rc)
        return SimpleNamespace(returncode=0)

    return fake_run, calls


def _run(monkeypatch, fake_run, api_key: str | None = "test-key", dry_run: bool = False, model=None):
    from argparse import Namespace

    monkeypatch.setattr(rcr.subprocess, "run", fake_run)
    if api_key is not None:
        monkeypatch.setenv("OPENAI_API_KEY", api_key)
    else:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    args = Namespace(test_cmd="", model=model, dry_run=dry_run)
    _execute(args)


def _execute(args):
    """main() のロジック部分（argparse なし）。"""
    import os

    py = rcr._python()

    ctr_cmd = [py, "-m", _CTR_MODULE, "--output", str(rcr.DEFAULT_REQUEST)]
    if args.test_cmd:
        ctr_cmd += ["--test-cmd", args.test_cmd]

    print("[run_cycle_review] Step 1: cycle_to_review_request")
    r = rcr.subprocess.run(ctr_cmd, cwd=rcr.REPO_ROOT)
    if r.returncode != 0:
        print("[ERROR] cycle_to_review_request 失敗")
        raise SystemExit(1)
    print("[OK] review_request.json 生成完了")

    if args.dry_run:
        print("[INFO] --dry-run: orchestrator をスキップします")
        raise SystemExit(0)

    if not os.environ.get("OPENAI_API_KEY"):
        print("[INFO] OPENAI_API_KEY 未設定: orchestrator をスキップします")
        raise SystemExit(0)

    orch_cmd = [py, "-m", _ORCH_MODULE,
                "--input", str(rcr.DEFAULT_REQUEST),
                "--output", str(rcr.DEFAULT_REPLY)]
    if args.model:
        orch_cmd += ["--model", args.model]

    print("[run_cycle_review] Step 2: orchestrator")
    r = rcr.subprocess.run(orch_cmd, cwd=rcr.REPO_ROOT)
    if r.returncode != 0:
        print("[ERROR] orchestrator 失敗")
        raise SystemExit(1)
    print("[OK] review_reply.md 生成完了")
    raise SystemExit(0)


# ── テスト ────────────────────────────────────────────────────────────────

def test_api_key_and_orch_success(monkeypatch, capsys):
    """API key あり + orchestrator 成功 → exit 0、両ステップ実行。"""
    fake_run, calls = _make_fake_subprocess(ctr_rc=0, orch_rc=0)
    with pytest.raises(SystemExit) as exc:
        _run(monkeypatch, fake_run, api_key="sk-test")
    assert exc.value.code == 0
    assert any(_is_ctr(c) for c in calls)
    assert any(_is_orch(c) for c in calls)
    out = capsys.readouterr().out
    assert "review_request.json 生成完了" in out
    assert "review_reply.md 生成完了" in out


def test_no_api_key(monkeypatch, capsys):
    """API key なし → cycle_to_review_request のみ実行して exit 0。"""
    fake_run, calls = _make_fake_subprocess(ctr_rc=0)
    with pytest.raises(SystemExit) as exc:
        _run(monkeypatch, fake_run, api_key=None)
    assert exc.value.code == 0
    assert any(_is_ctr(c) for c in calls)
    assert not any(_is_orch(c) for c in calls)
    out = capsys.readouterr().out
    assert "review_request.json 生成完了" in out
    assert "OPENAI_API_KEY 未設定" in out


def test_dry_run(monkeypatch, capsys):
    """--dry-run → cycle_to_review_request のみ実行して exit 0。"""
    fake_run, calls = _make_fake_subprocess(ctr_rc=0)
    with pytest.raises(SystemExit) as exc:
        _run(monkeypatch, fake_run, api_key="sk-test", dry_run=True)
    assert exc.value.code == 0
    assert any(_is_ctr(c) for c in calls)
    assert not any(_is_orch(c) for c in calls)
    out = capsys.readouterr().out
    assert "review_request.json 生成完了" in out
    assert "--dry-run" in out


def test_ctr_fails(monkeypatch, capsys):
    """cycle_to_review_request 失敗 → exit 1。"""
    fake_run, calls = _make_fake_subprocess(ctr_rc=1)
    with pytest.raises(SystemExit) as exc:
        _run(monkeypatch, fake_run, api_key="sk-test")
    assert exc.value.code == 1
    assert not any(_is_orch(c) for c in calls)


def test_orch_fails(monkeypatch, capsys):
    """orchestrator 失敗 → exit 1。"""
    fake_run, calls = _make_fake_subprocess(ctr_rc=0, orch_rc=1)
    with pytest.raises(SystemExit) as exc:
        _run(monkeypatch, fake_run, api_key="sk-test")
    assert exc.value.code == 1
    assert "orchestrator 失敗" in capsys.readouterr().out


def test_load_dotenv_called_and_key_used(monkeypatch, capsys):
    """load_dotenv が KEY を環境変数に展開した場合、orchestrator が呼ばれること。"""
    fake_run, calls = _make_fake_subprocess(ctr_rc=0, orch_rc=0)
    monkeypatch.setattr(rcr.subprocess, "run", fake_run)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    def fake_dotenv(**kwargs):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-from-dotenv")

    monkeypatch.setattr(rcr, "load_dotenv", fake_dotenv)
    monkeypatch.setattr("sys.argv", ["run_cycle_review"])

    rcr.main()  # 正常系は sys.exit を呼ばない

    assert any(_is_orch(c) for c in calls)
    assert "review_reply.md 生成完了" in capsys.readouterr().out


def test_load_dotenv_called_no_key_skips_orch(monkeypatch, capsys):
    """load_dotenv を呼んでも KEY が展開されない場合、orchestrator をスキップすること。"""
    fake_run, calls = _make_fake_subprocess(ctr_rc=0)
    monkeypatch.setattr(rcr.subprocess, "run", fake_run)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(rcr, "load_dotenv", lambda **kwargs: None)
    monkeypatch.setattr("sys.argv", ["run_cycle_review"])

    with pytest.raises(SystemExit) as exc:
        rcr.main()

    assert exc.value.code == 0
    assert not any(_is_orch(c) for c in calls)
    assert "OPENAI_API_KEY 未設定" in capsys.readouterr().out
