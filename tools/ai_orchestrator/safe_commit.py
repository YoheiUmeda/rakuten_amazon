# tools/ai_orchestrator/safe_commit.py
"""
安全柵付き git commit ラッパー。

abort 条件:
  - staged files なし
  - Important files (CLAUDE.md 定義) を含む
  - secrets ファイル名パターンを含む (.env / *.env / *credentials* / *secret* / *token*)
  - commit message が空

scope 外ファイルは WARNING のみ（abort しない）。
git commit --amend / --no-verify / push / reset / rebase は対象外。

usage:
    python -m tools.ai_orchestrator.safe_commit -m "feat: add foo"
"""
from __future__ import annotations

import argparse
import fnmatch
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# CLAUDE.md の ## Important files と同期
IMPORTANT_FILES = {
    "amazon_fee.py",
    "price_calculation.py",
    "batch_runner.py",
    "main.py",
    "keepa_client.py",
    "get_keepa_prices.py",
    "rakuten_client.py",
    "spapi_client.py",
    "app/schemas.py",
    "app/db.py",
    "app/repository.py",
    "app/main_fastapi.py",
}

# ファイル名ベースの secrets パターン
SECRETS_PATTERNS = [
    ".env",
    "*.env",
    "*credentials*",
    "*secret*",
    "*token*",
]

# auto-allow スコープ（scope 外は WARNING のみ）
ALLOWED_SCOPE_PATTERNS = [
    "tools/ai_orchestrator/*",
    "tests/test_cycle_manager.py",
    "tests/test_loop_runner.py",
    "tests/test_cycle_to_review_request.py",
    "tests/test_run_cycle_review.py",
    "tests/test_safe_commit.py",
    "docs/automation/auto_mode_spec.md",
    "CLAUDE.md",
]


def _get_staged_files() -> list[str]:
    r = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    return [f.strip() for f in r.stdout.splitlines() if f.strip()]


def _is_important(filepath: str) -> bool:
    name = Path(filepath).name
    # 完全一致 or パス末尾一致
    return filepath in IMPORTANT_FILES or name in IMPORTANT_FILES


def _is_secrets(filepath: str) -> bool:
    name = Path(filepath).name
    for pat in SECRETS_PATTERNS:
        if fnmatch.fnmatch(name, pat) or fnmatch.fnmatch(filepath, pat):
            return True
    return False


def _is_in_scope(filepath: str) -> bool:
    for pat in ALLOWED_SCOPE_PATTERNS:
        if fnmatch.fnmatch(filepath, pat):
            return True
    return False


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="安全柵付き git commit")
    parser.add_argument("-m", "--message", required=True, help="commit message")
    args = parser.parse_args()

    msg = args.message.strip()

    # ── commit message チェック ───────────────────────────────────────────
    if not msg:
        print("[ERROR] commit message が空です")
        sys.exit(1)

    # ── staged files チェック ─────────────────────────────────────────────
    staged = _get_staged_files()
    if not staged:
        print("[ERROR] staged files がありません。git add を先に実行してください")
        sys.exit(1)

    # ── Important files チェック ──────────────────────────────────────────
    important_hits = [f for f in staged if _is_important(f)]
    if important_hits:
        print("[ERROR] Important files が staged に含まれています。手動で commit してください:")
        for f in important_hits:
            print(f"  {f}")
        sys.exit(1)

    # ── secrets ファイル名チェック ────────────────────────────────────────
    secrets_hits = [f for f in staged if _is_secrets(f)]
    if secrets_hits:
        print("[ERROR] secrets ファイルが staged に含まれています:")
        for f in secrets_hits:
            print(f"  {f}")
        sys.exit(1)

    # ── scope 外 WARNING ──────────────────────────────────────────────────
    out_of_scope = [f for f in staged if not _is_in_scope(f)]
    if out_of_scope:
        print("[WARNING] auto-allow スコープ外のファイルが含まれています:")
        for f in out_of_scope:
            print(f"  {f}")

    # ── commit 実行 ───────────────────────────────────────────────────────
    print(f"[INFO] staged ({len(staged)} files): {', '.join(staged)}")
    r = subprocess.run(
        ["git", "commit", "-m", msg],
        cwd=REPO_ROOT,
    )
    if r.returncode != 0:
        print("[ERROR] git commit 失敗")
        sys.exit(1)
    print("[OK] committed")


if __name__ == "__main__":
    main()
