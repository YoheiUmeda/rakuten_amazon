# tests/test_run_batch_cli.py
"""run_batch_cli の load_query_files が OS 環境変数を優先することを確認するテスト。"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from run_batch_cli import load_query_files


def test_load_query_files_uses_os_env_over_default(tmp_path, monkeypatch):
    """KEEPA_QUERY_DIR を OS 環境変数で指定したとき、そのフォルダが使われる。"""
    query_file = tmp_path / "test_query.txt"
    query_file.write_text("https://example.com/query", encoding="utf-8")

    monkeypatch.setenv("KEEPA_QUERY_DIR", str(tmp_path))

    result = load_query_files(Path("."))
    names = [p.name for p, _ in result]
    assert "test_query.txt" in names


def test_load_query_files_env_takes_priority_over_default(tmp_path, monkeypatch):
    """KEEPA_QUERY_DIR が設定されていれば data/queries/ よりも優先される。"""
    query_file = tmp_path / "env_query.txt"
    query_file.write_text("https://example.com/env", encoding="utf-8")

    monkeypatch.setenv("KEEPA_QUERY_DIR", str(tmp_path))

    result = load_query_files(Path("."))
    names = [p.name for p, _ in result]
    assert names == ["env_query.txt"]


def test_import_does_not_overwrite_os_env():
    """batch_runner 等を import しても OS 環境変数が保持されること。

    override=True だと import 時に .env 値で OS 変数が上書きされる。
    このテストでは import 前後で os.environ の値が変わらないことを確認する。
    """
    sentinel = "__TEST_SENTINEL_VALUE__"
    os.environ["KEEPA_QUERY_DIR"] = sentinel
    try:
        # import（キャッシュ済みなら reload で再実行）
        import importlib
        import batch_runner  # noqa: F401
        importlib.reload(batch_runner)
        assert os.environ.get("KEEPA_QUERY_DIR") == sentinel, (
            "batch_runner import が OS 環境変数 KEEPA_QUERY_DIR を上書きした"
        )
    finally:
        del os.environ["KEEPA_QUERY_DIR"]


def test_subprocess_keepa_query_dir_survives_import():
    """subprocess 経由で KEEPA_QUERY_DIR を渡したとき、import 後も値が保持されること。

    この不具合の再現テスト:
    override=True の場合、subprocess に渡した KEEPA_QUERY_DIR が
    batch_runner import 時の load_dotenv(override=True) で .env 値に上書きされる。
    """
    repo_root = Path(__file__).parents[1]
    code = (
        "import os; "
        "os.environ.setdefault('KEEPA_QUERY_DIR', 'SHOULD_NOT_BE_SET'); "
        "import batch_runner; "  # load_dotenv が走る
        "print(os.environ.get('KEEPA_QUERY_DIR', ''))"
    )
    env = os.environ.copy()
    env["KEEPA_QUERY_DIR"] = "data/queries_test"

    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        env=env,
    )
    output = result.stdout.strip()
    assert output == "data/queries_test", (
        f"KEEPA_QUERY_DIR が保持されなかった: {output!r}"
    )
