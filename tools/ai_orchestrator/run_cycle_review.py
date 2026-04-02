# tools/ai_orchestrator/run_cycle_review.py
"""
pending_review 状態の cycle_state.json を受けて
cycle_to_review_request → orchestrator を順に実行するラッパー。

fail-open:
  - OPENAI_API_KEY 未設定 → orchestrator をスキップして exit 0
  - --dry-run              → orchestrator をスキップして exit 0
fail-close:
  - cycle_to_review_request 失敗 → exit 1
  - orchestrator 失敗（APIエラー等）→ exit 1

usage:
    python -m tools.ai_orchestrator.run_cycle_review
    python -m tools.ai_orchestrator.run_cycle_review \\
        --test-cmd "venv/Scripts/python -m pytest tests/ -q" \\
        --model gpt-4o-mini
    python -m tools.ai_orchestrator.run_cycle_review --dry-run
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
VENV_PYTHON = REPO_ROOT / "venv" / "Scripts" / "python.exe"
DEFAULT_REQUEST = REPO_ROOT / ".ai" / "handoff" / "review_request.json"
DEFAULT_REPLY = REPO_ROOT / "docs" / "handoff" / "review_reply.md"


def _python() -> str:
    return str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="pending_review → review_request.json → review_reply.md"
    )
    parser.add_argument("--test-cmd", default="", help="テストコマンド（任意）")
    parser.add_argument("--model", default=None, help="OpenAI モデル（省略時: OPENAI_MODEL env）")
    parser.add_argument("--dry-run", action="store_true", help="orchestrator をスキップ")
    args = parser.parse_args()

    py = _python()

    # ── Step 1: cycle_to_review_request ──────────────────────────────────
    ctr_cmd = [py, "-m", "tools.ai_orchestrator.cycle_to_review_request",
               "--output", str(DEFAULT_REQUEST)]
    if args.test_cmd:
        ctr_cmd += ["--test-cmd", args.test_cmd]

    print("[run_cycle_review] Step 1: cycle_to_review_request")
    r = subprocess.run(ctr_cmd, cwd=REPO_ROOT)
    if r.returncode != 0:
        print("[ERROR] cycle_to_review_request 失敗。処理を中断します")
        sys.exit(1)
    print(f"[OK] review_request.json 生成完了: {DEFAULT_REQUEST}")

    # ── --dry-run ─────────────────────────────────────────────────────────
    if args.dry_run:
        print("[INFO] --dry-run: orchestrator をスキップします")
        sys.exit(0)

    # ── OPENAI_API_KEY チェック（.env から読み込んでから確認）────────────
    load_dotenv()
    if not os.environ.get("OPENAI_API_KEY"):
        print("[INFO] OPENAI_API_KEY 未設定: orchestrator をスキップします")
        print(f"       review_request.json は生成済みです: {DEFAULT_REQUEST}")
        sys.exit(0)

    # ── Step 2: orchestrator ──────────────────────────────────────────────
    orch_cmd = [py, "-m", "tools.ai_orchestrator.orchestrator",
                "--input", str(DEFAULT_REQUEST),
                "--output", str(DEFAULT_REPLY)]
    if args.model:
        orch_cmd += ["--model", args.model]

    print("\n[run_cycle_review] Step 2: orchestrator")
    r = subprocess.run(orch_cmd, cwd=REPO_ROOT)
    if r.returncode != 0:
        print("[ERROR] orchestrator 失敗")
        sys.exit(1)
    print(f"[OK] review_reply.md 生成完了: {DEFAULT_REPLY}")
    print()
    print("次のステップ: review_reply.md を確認後:")
    print("  venv/Scripts/python -m tools.ai_orchestrator.apply_review --auto-approve --auto-archive")
    print("  git push")


if __name__ == "__main__":
    main()
