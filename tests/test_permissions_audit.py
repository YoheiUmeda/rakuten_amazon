# tests/test_permissions_audit.py
"""permissions_audit の最小テスト。"""
from __future__ import annotations

import argparse
import json

import pytest

import tools.ai_orchestrator.permissions_audit as pa


def _make_args(**kwargs) -> argparse.Namespace:
    defaults = dict(path="")
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


@pytest.fixture()
def valid_settings(tmp_path):
    f = tmp_path / "settings.local.json"
    f.write_text(json.dumps({
        "permissions": {
            "defaultMode": "acceptEdits",
            "allow": ["Bash(git status)"],
            "ask": ["Bash(git push *)"],
            "deny": ["Bash(rm -rf *)"],
        }
    }), encoding="utf-8")
    return f


@pytest.fixture()
def invalid_settings(tmp_path):
    f = tmp_path / "settings.local.json"
    f.write_text("{invalid json", encoding="utf-8")
    return f


# ── validate-settings ─────────────────────────────────────────────────────

def test_validate_valid(valid_settings, capsys):
    ret = pa.cmd_validate(_make_args(path=str(valid_settings)))
    assert ret == 0
    assert "[OK]" in capsys.readouterr().out


def test_validate_invalid(invalid_settings, capsys):
    ret = pa.cmd_validate(_make_args(path=str(invalid_settings)))
    assert ret == 1
    assert "[ERROR]" in capsys.readouterr().out


def test_validate_missing(tmp_path, capsys):
    ret = pa.cmd_validate(_make_args(path=str(tmp_path / "nonexistent.json")))
    assert ret == 1


# ── summarize-settings ────────────────────────────────────────────────────

def test_summarize_counts(valid_settings, capsys):
    ret = pa.cmd_summarize(_make_args(path=str(valid_settings)))
    assert ret == 0
    out = capsys.readouterr().out
    assert "allow       : 1 件" in out
    assert "ask         : 1 件" in out
    assert "deny        : 1 件" in out
    assert "acceptEdits" in out


def test_summarize_invalid(invalid_settings, capsys):
    ret = pa.cmd_summarize(_make_args(path=str(invalid_settings)))
    assert ret == 1
