# tools/ai_orchestrator/loop_runner.py
"""
確認不要モード Phase 2: 1ループ分の submit フローを自動化する CLI。

フロー:
  [pre-flight dirty check]
  → [state 確認 / 新規 start]
  → [テスト実行]
  → pass: record → submit → review_summary 生成
          [--auto-review 時] → run_cycle_review 実行
          → exit 0
  → fail: record → exit 1  (submit しない)

usage:
    python -m tools.ai_orchestrator.loop_runner \\
        --test-cmd "venv/Scripts/python -m pytest tests/ -q --tb=short" \\
        --files src/foo.py src/bar.py \\
        --summary "foo を修正" \\
        [--goal "XX を修正"]       # state 不在時のみ必須
        [--auto-review]            # submit 成功後に run_cycle_review を自動実行
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

from tools.ai_orchestrator.cycle_manager import (
    REPO_ROOT,
    _git_short_hash,
    cmd_record,
    cmd_start,
    cmd_submit,
    load_state,
)
from tools.ai_orchestrator.review_summary import OUTPUT_PATH, build_summary


def _check_clean() -> bool:
    """working tree・index・untracked すべてが clean なら True。"""
    r = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=normal"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    return r.stdout.strip() == ""


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="1ループ分の submit フローを自動化する")
    parser.add_argument("--goal", default="", help="サイクルの目的（state 不在時のみ必須）")
    parser.add_argument("--test-cmd", required=True, help="テスト実行コマンド")
    parser.add_argument("--files", nargs="+", required=True, help="変更ファイル一覧")
    parser.add_argument("--summary", required=True, help="このループの1行要約")
    parser.add_argument("--auto-review", action="store_true",
                        help="submit 成功後に run_cycle_review を自動実行する")
    args = parser.parse_args()

    # ── pre-flight: dirty check ───────────────────────────────────────────
    if not _check_clean():
        print("[ERROR] working tree が dirty です。コミットしてから実行してください")
        sys.exit(1)

    # ── state 確認 ────────────────────────────────────────────────────────
    state = load_state()
    status = state.get("status") if state else None

    if not state:
        if not args.goal:
            print("[ERROR] state がありません。--goal を指定してください")
            sys.exit(1)
        ret = cmd_start(Namespace(goal=args.goal))
        if ret != 0:
            sys.exit(ret)
    elif status == "in_progress":
        pass  # --goal は無視して継続
    else:
        print(f"[ERROR] status={status!r} は loop_runner で続行できません")
        print("  pending_review → approve / reject で解決してから実行してください")
        sys.exit(1)

    # ── テスト実行 ────────────────────────────────────────────────────────
    print(f"[INFO] テスト実行: {args.test_cmd}")
    result = subprocess.run(args.test_cmd, shell=True, cwd=REPO_ROOT)
    test_result = "pass" if result.returncode == 0 else "fail"
    print(f"[INFO] test={test_result}")

    commit = _git_short_hash()

    # ── record ────────────────────────────────────────────────────────────
    ret = cmd_record(Namespace(
        commit=commit,
        files=args.files,
        test=test_result,
        summary=args.summary,
    ))
    if ret != 0:
        sys.exit(ret)

    # ── 結果分岐 ──────────────────────────────────────────────────────────
    if test_result == "pass":
        ret = cmd_submit(Namespace())
        if ret != 0:
            sys.exit(ret)

        content = build_summary(load_state())
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(content, encoding="utf-8")
        print(f"[OK] review_summary 生成: {OUTPUT_PATH}")

        if args.auto_review:
            print("[INFO] --auto-review: run_cycle_review を実行します")
            venv_py = REPO_ROOT / "venv" / "Scripts" / "python.exe"
            py = str(venv_py) if venv_py.exists() else sys.executable
            r = subprocess.run(
                [py, "-m", "tools.ai_orchestrator.run_cycle_review"],
                cwd=REPO_ROOT,
            )
            if r.returncode != 0:
                print("[ERROR] run_cycle_review 失敗")
                sys.exit(1)
            print("[OK] run_cycle_review 完了")

        sys.exit(0)
    else:
        print("[ERROR] テスト失敗。修正後に再実行してください")
        sys.exit(1)


if __name__ == "__main__":
    main()
