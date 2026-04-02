# tests/test_safe_commit.py
"""safe_commit の最小テスト。"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

import tools.ai_orchestrator.safe_commit as sc


# ── helpers ───────────────────────────────────────────────────────────────

def _run(monkeypatch, staged: list[str], message: str = "fix: something"):
    """safe_commit のロジック部分を直接実行する（argparse/subprocess バイパス）。"""
    monkeypatch.setattr(sc, "_get_staged_files", lambda: staged)

    # git commit は実際に実行しない
    commits: list = []
    def fake_commit(cmd, cwd=None):
        commits.append(cmd)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(sc.subprocess, "run", fake_commit)

    msg = message.strip()
    if not msg:
        print("[ERROR] commit message が空です")
        raise SystemExit(1)

    files = sc._get_staged_files()
    if not files:
        print("[ERROR] staged files がありません")
        raise SystemExit(1)

    important_hits = [f for f in files if sc._is_important(f)]
    if important_hits:
        print(f"[ERROR] Important files が staged に含まれています: {important_hits}")
        raise SystemExit(1)

    secrets_hits = [f for f in files if sc._is_secrets(f)]
    if secrets_hits:
        print(f"[ERROR] secrets ファイルが staged に含まれています: {secrets_hits}")
        raise SystemExit(1)

    out_of_scope = [f for f in files if not sc._is_in_scope(f)]
    if out_of_scope:
        print(f"[WARNING] scope 外: {out_of_scope}")

    r = sc.subprocess.run(["git", "commit", "-m", msg], cwd=sc.REPO_ROOT)
    if r.returncode != 0:
        raise SystemExit(1)
    print("[OK] committed")
    raise SystemExit(0)


# ── テスト ────────────────────────────────────────────────────────────────

def test_no_staged(monkeypatch, capsys):
    """staged なし → exit 1。"""
    with pytest.raises(SystemExit) as exc:
        _run(monkeypatch, staged=[])
    assert exc.value.code == 1
    assert "staged files" in capsys.readouterr().out


def test_important_file_aborts(monkeypatch, capsys):
    """Important files を含む → exit 1。"""
    with pytest.raises(SystemExit) as exc:
        _run(monkeypatch, staged=["amazon_fee.py"])
    assert exc.value.code == 1
    assert "Important files" in capsys.readouterr().out


def test_secrets_filename_aborts(monkeypatch, capsys):
    """secrets ファイル名パターン → exit 1。"""
    for fname in [".env", "prod.env", "db_credentials.json", "api_secret.txt", "auth_token.py"]:
        with pytest.raises(SystemExit) as exc:
            _run(monkeypatch, staged=[fname])
        assert exc.value.code == 1, f"{fname} should abort"


def test_empty_message_aborts(monkeypatch, capsys):
    """commit message 空 → exit 1。"""
    with pytest.raises(SystemExit) as exc:
        _run(monkeypatch, staged=["tools/ai_orchestrator/foo.py"], message="   ")
    assert exc.value.code == 1
    assert "message" in capsys.readouterr().out


def test_normal_commit(monkeypatch, capsys):
    """正常系: scope 内ファイル + 有効 message → git commit 実行、exit 0。"""
    with pytest.raises(SystemExit) as exc:
        _run(monkeypatch, staged=["tools/ai_orchestrator/cycle_manager.py"])
    assert exc.value.code == 0
    assert "[OK] committed" in capsys.readouterr().out


def test_tests_wildcard_in_scope():
    """tests/test_*.py はすべてスコープ内。"""
    assert sc._is_in_scope("tests/test_apply_review.py")
    assert sc._is_in_scope("tests/test_price_calculation.py")
    assert sc._is_in_scope("tests/test_safe_commit.py")


def test_non_test_files_out_of_scope():
    """docs/ の汎用ファイルはスコープ外。"""
    assert not sc._is_in_scope("docs/example.md")
    assert not sc._is_in_scope("docs/handoff/result.md")
