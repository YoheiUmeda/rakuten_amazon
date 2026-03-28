# tools/ai_orchestrator/run_review.py
"""
generate_review_request + orchestrator を一発実行するラッパー。

fail-open: orchestrator 失敗時も exit 0 で終了し、開発を止めない。
opt-in: 手動実行のみ。git hook に自動連携しない。

usage:
    # staged 変更を対象に全ステップ実行
    venv/Scripts/python -m tools.ai_orchestrator.run_review \\
      --task "タスク説明" \\
      --staged \\
      [--test-cmd "python -m pytest tests/ -v" --run-tests]

    # generate のみ（orchestrator スキップ）
    venv/Scripts/python -m tools.ai_orchestrator.run_review \\
      --task "タスク説明" --staged --dry-run

    # review_request.json を保存して止まる（中身確認用）
    venv/Scripts/python -m tools.ai_orchestrator.run_review \\
      --task "タスク説明" --staged --save-only
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from tools.ai_orchestrator.openai_client import DEFAULT_MODEL

REPO_ROOT      = Path(__file__).resolve().parents[2]
VENV_PYTHON    = REPO_ROOT / "venv" / "Scripts" / "python.exe"
DEFAULT_INPUT  = REPO_ROOT / ".ai" / "handoff" / "review_request.json"
DEFAULT_OUTPUT = REPO_ROOT / "docs" / "review_reply.md"
LOG_PATH       = REPO_ROOT / ".ai" / "logs" / "review_runs.jsonl"


def _python() -> str:
    return str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable


def _append_history(entry: dict) -> None:
    """実行履歴を review_runs.jsonl に1行追記する。書き込み失敗は無視（fail-open）。"""
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _show_history(n: int) -> None:
    """直近 n 件の履歴を整形して stdout に表示する。"""
    if not LOG_PATH.exists():
        print("[run_review] 履歴なし")
        return
    lines = [ln for ln in LOG_PATH.read_text(encoding="utf-8").splitlines() if ln.strip()]
    recent = lines[-n:] if len(lines) > n else lines
    print(f"\n[run_review] 直近 {len(recent)} 件:")
    for line in recent:
        try:
            e = json.loads(line)
            ts = e.get("timestamp", "")[:19].replace("T", " ")
            ok = "ok" if e.get("success") else "NG"
            print(f"  {ts}  {e.get('mode',''):10} {e.get('model',''):15} [{ok}]  {e.get('task','')[:40]}")
        except Exception:
            print(f"  {line[:100]}")


def _print_json_summary(path: Path) -> None:
    """保存済み review_request.json の要約を stdout に表示する。ファイル不在・破損時はスキップ。"""
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    print("\n[run_review] --- review_request.json 要約 ---")
    print(f"  task       : {data.get('task', '')[:80]}")
    model = data.get("model", "")
    if model:
        print(f"  model      : {model}")
    files = data.get("changed_files", [])
    files_str = ", ".join(files) if files else "(なし)"
    print(f"  files ({len(files):2d}) : {files_str}")
    q = data.get("open_questions", [])
    if q:
        print(f"  questions  : {len(q)} 件")
    test_out = data.get("test_output", "")
    if test_out:
        preview = test_out[:120].replace("\n", " ")
        suffix = "..." if len(test_out) > 120 else ""
        print(f"  test_output: {preview}{suffix}")
    print("[run_review] -----------------------------------")


def run(args: argparse.Namespace) -> None:
    """コアロジック。テストから直接呼べるよう main() から分離。"""

    # --history-tail: 履歴表示して終了
    if getattr(args, "history_tail", 0):
        _show_history(args.history_tail)
        return

    py = _python()

    # 履歴エントリーを準備（各終了点で _append_history を呼ぶ）
    resolved_model = getattr(args, "model", None) or os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
    mode = "dry-run" if args.dry_run else ("save-only" if getattr(args, "save_only", False) else "full-step")
    h: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "model": resolved_model,
        "task": args.task[:80],
        "test_command": args.test_cmd or "",
        "changed_files_count": 0,
        "api_status": "skipped",
        "output_path": "",
        "success": False,
    }

    # ── Step 1: generate_review_request ──────────────────────────────────
    gen_cmd = [py, "-m", "tools.ai_orchestrator.generate_review_request",
               "--task", args.task,
               "--output", str(DEFAULT_INPUT)]
    if args.staged:                              gen_cmd.append("--staged")
    if args.files:                               gen_cmd += ["--files"]          + args.files
    if args.test_cmd:                            gen_cmd += ["--test-cmd",         args.test_cmd]
    if args.run_tests:                           gen_cmd.append("--run-tests")
    if getattr(args, "related_code", []):        gen_cmd += ["--related-code"]   + args.related_code
    if args.open_questions:                      gen_cmd += ["--open-questions"]  + args.open_questions
    if args.constraints:                         gen_cmd += ["--constraints"]     + args.constraints
    if args.dry_run:                             gen_cmd.append("--dry-run")
    if getattr(args, "model", None):             gen_cmd += ["--model",           args.model]

    print("[run_review] Step 1: generate_review_request")
    try:
        r = subprocess.run(gen_cmd, cwd=REPO_ROOT, timeout=300)
    except subprocess.TimeoutExpired:
        print("[run_review][WARN] generate タイムアウト（300s）。fail-open: exit 0.",
              file=sys.stderr)
        _append_history(h)
        sys.exit(0)
    if r.returncode != 0:
        print("[run_review][WARN] generate 失敗。処理を中断します（fail-open: exit 0）.",
              file=sys.stderr)
        _append_history(h)
        sys.exit(0)

    # changed_files_count: --files 指定時は直接カウント（dry-run でも正確）
    # staged + dry-run の場合のみ 0 のまま（git 呼び出しを避けるため）
    if args.files:
        h["changed_files_count"] = len(args.files)
    elif not args.dry_run and DEFAULT_INPUT.exists():
        try:
            h["changed_files_count"] = len(
                json.loads(DEFAULT_INPUT.read_text(encoding="utf-8")).get("changed_files", [])
            )
        except Exception:
            pass

    if args.dry_run:
        print("[run_review] --dry-run: orchestrator はスキップ。")
        h["success"] = True
        _append_history(h)
        return

    if getattr(args, "save_only", False):
        print(f"[run_review] --save-only: review_request.json 保存済み。orchestrator はスキップ。")
        print(f"[run_review] 確認: {DEFAULT_INPUT}")
        _print_json_summary(DEFAULT_INPUT)
        h["success"] = True
        _append_history(h)
        return

    # ── Step 2: orchestrator（fail-open） ─────────────────────────────────
    orch_cmd = [py, "-m", "tools.ai_orchestrator.orchestrator",
                "--input",  str(DEFAULT_INPUT),
                "--output", str(DEFAULT_OUTPUT)]
    if getattr(args, "model", None):             orch_cmd += ["--model", args.model]
    print("\n[run_review] Step 2: orchestrator")
    try:
        r = subprocess.run(orch_cmd, cwd=REPO_ROOT, timeout=300)
    except subprocess.TimeoutExpired:
        print("[run_review][WARN] orchestrator タイムアウト（300s）。fail-open: exit 0.",
              file=sys.stderr)
        h["api_status"] = "timeout"
        _append_history(h)
        sys.exit(0)
    if r.returncode != 0:
        print("[run_review][WARN] orchestrator 失敗。review_reply.md なしで続行可（fail-open）.",
              file=sys.stderr)
        h["api_status"] = "failed"
        _append_history(h)
        sys.exit(0)

    h["api_status"] = "ok"
    h["output_path"] = str(DEFAULT_OUTPUT)
    h["success"] = True
    _append_history(h)
    print(f"\n[run_review] 完了。確認: {DEFAULT_OUTPUT}")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="generate_review_request + orchestrator を一発実行（fail-open）"
    )
    parser.add_argument("--task",           default=None)
    parser.add_argument("--staged",         action="store_true")
    parser.add_argument("--files",          nargs="*", default=[])
    parser.add_argument("--test-cmd",       default="")
    parser.add_argument("--run-tests",      action="store_true")
    parser.add_argument("--related-code",   nargs="*", default=[], metavar="F")
    parser.add_argument("--open-questions", nargs="*", default=[], metavar="Q")
    parser.add_argument("--constraints",    nargs="*", default=[], metavar="C")
    parser.add_argument("--dry-run",        action="store_true",
                        help="generate のみ実行（orchestrator をスキップ）")
    parser.add_argument("--save-only",      action="store_true",
                        help="review_request.json を保存して終了（orchestrator をスキップ）")
    parser.add_argument("--model",          default=None,
                        help="使用モデル（省略時: OPENAI_MODEL env → gpt-4o-mini）")
    parser.add_argument("--history-tail",   type=int, default=0, metavar="N",
                        help="直近 N 件の履歴を表示して終了（--task 不要）")
    args = parser.parse_args()

    # --history-tail は --task なしで動作する
    if args.history_tail:
        _show_history(args.history_tail)
        return

    if not args.task:
        parser.error("--task is required")

    run(args)


if __name__ == "__main__":
    main()
