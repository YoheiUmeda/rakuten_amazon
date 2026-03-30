# tools/ai_orchestrator/cycle_manager.py
"""
確認不要モード Phase 1: サイクル状態管理 CLI。

usage:
    python -m tools.ai_orchestrator.cycle_manager start --goal "XX を修正"
    python -m tools.ai_orchestrator.cycle_manager record \\
        --commit abc1234 --files f1.py f2.py --test pass --summary "修正完了"
    python -m tools.ai_orchestrator.cycle_manager ng --reason "テスト失敗"
    python -m tools.ai_orchestrator.cycle_manager done
    python -m tools.ai_orchestrator.cycle_manager status
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = REPO_ROOT / ".ai" / "state" / "cycle_state.json"
SOFT_LIMIT = 10


def _now_jst() -> str:
    jst = timezone(timedelta(hours=9))
    return datetime.now(jst).isoformat(timespec="seconds")


def _git_short_hash() -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def load_state() -> dict:
    if not STATE_PATH.exists():
        return {}
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def cmd_start(args: argparse.Namespace) -> int:
    state = load_state()
    current = state.get("status")
    if current in ("in_progress", "pending_review"):
        print(f"[WARN] サイクルがすでに {current} です (goal: {state.get('goal')})")
        if current == "in_progress":
            print("  続行するには先に submit / stop で閉じてください")
        else:
            print("  続行するには先に approve / reject / stop で閉じてください")
        return 1
    cycle_id = datetime.now(timezone(timedelta(hours=9))).strftime("%Y%m%d-%H%M%S")
    base_commit = _git_short_hash()
    state = {
        "cycle_id": cycle_id,
        "goal": args.goal,
        "status": "in_progress",
        "loop_count": 0,
        "base_commit": base_commit,
        "last_good_commit": None,
        "stop_reason": None,
        "ng_history": [],
        "loops": [],
    }
    save_state(state)
    print(f"[OK] cycle started: {cycle_id}")
    print(f"     goal: {args.goal}")
    print(f"     base_commit: {base_commit or '(none)'}")
    return 0


def cmd_record(args: argparse.Namespace) -> int:
    state = load_state()
    if not state:
        print("[ERROR] サイクルが開始されていません。先に start を実行してください")
        return 1
    if state.get("status") != "in_progress":
        print(f"[ERROR] status が in_progress ではありません: {state.get('status')}")
        return 1

    pre_commit = _git_short_hash()
    loop_id = state["loop_count"] + 1
    state["loop_count"] = loop_id
    state["loops"].append({
        "loop_id": loop_id,
        "timestamp": _now_jst(),
        "pre_commit": pre_commit,
        "commit": args.commit or "",
        "changed_files": args.files or [],
        "test_result": args.test,
        "summary": args.summary or "",
    })
    if args.test == "pass":
        state["last_good_commit"] = args.commit or pre_commit
    save_state(state)
    print(f"[OK] loop {loop_id} recorded  test={args.test}  commit={args.commit or '(none)'}  pre={pre_commit or '(none)'}")
    if loop_id > SOFT_LIMIT:
        print(f"[WARNING] loop_count ({loop_id}) がソフトリミット ({SOFT_LIMIT}) を超えました。人間確認を推奨します")
    return 0


def cmd_submit(args: argparse.Namespace) -> int:
    state = load_state()
    if not state:
        print("[ERROR] サイクルが開始されていません")
        return 1
    if state.get("status") != "in_progress":
        print(f"[ERROR] submit は in_progress の時のみ実行できます (current: {state.get('status')})")
        return 1
    if not state.get("loops"):
        print("[ERROR] ループが1件もありません。先に record を実行してください")
        return 1
    state["status"] = "pending_review"
    save_state(state)
    print(f"[OK] status: pending_review")
    print("     review_summary を生成してレビューを依頼してください:")
    print("       python -m tools.ai_orchestrator.review_summary")
    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    state = load_state()
    if not state:
        print("[ERROR] サイクルが開始されていません")
        return 1
    if state.get("status") != "pending_review":
        print(f"[ERROR] approve は pending_review の時のみ実行できます (current: {state.get('status')})")
        return 1
    state["status"] = "done"
    save_state(state)
    print(f"[OK] approved. cycle done: {state.get('cycle_id')}")
    print("     push 候補です。git push origin main を実行してください")
    return 0


def cmd_reject(args: argparse.Namespace) -> int:
    state = load_state()
    if not state:
        print("[ERROR] サイクルが開始されていません")
        return 1
    if state.get("status") != "pending_review":
        print(f"[ERROR] reject は pending_review の時のみ実行できます (current: {state.get('status')})")
        return 1
    reason = args.reason or ""
    if not reason:
        print("[ERROR] reject には --reason が必須です")
        return 1
    if "ng_history" not in state:
        state["ng_history"] = []
    state["ng_history"].append({"timestamp": _now_jst(), "reason": reason})
    state["last_reject_reason"] = reason
    state["status"] = "in_progress"
    save_state(state)
    print(f"[OK] rejected (#{len(state['ng_history'])}). reason: {reason}")
    print("     修正後 record → submit で再提出してください")
    return 0


def cmd_ng(args: argparse.Namespace) -> int:
    import warnings
    print("[DEPRECATED] ng は非推奨です。reject を使用してください", file=sys.stderr)
    state = load_state()
    if not state:
        print("[ERROR] サイクルが開始されていません")
        return 1
    reason = args.reason or ""
    if "ng_history" not in state:
        state["ng_history"] = []
    state["ng_history"].append({"timestamp": _now_jst(), "reason": reason})
    state["stop_reason"] = reason
    state["status"] = "in_progress"
    save_state(state)
    print(f"[OK] NG recorded (#{len(state['ng_history'])}). reason: {reason}")
    print("     次のループへ進んでください")
    return 0


def cmd_done(args: argparse.Namespace) -> int:
    """approve の alias。"""
    return cmd_approve(args)


def cmd_stop(args: argparse.Namespace) -> int:
    state = load_state()
    if not state:
        print("[ERROR] サイクルが開始されていません")
        return 1
    state["status"] = "stopped"
    state["stop_reason"] = args.reason or "manual stop"
    save_state(state)
    print(f"[OK] cycle stopped. reason: {state['stop_reason']}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    state = load_state()
    if not state:
        print("[INFO] サイクルなし (.ai/state/cycle_state.json が存在しません)")
        return 0
    print(f"cycle_id        : {state.get('cycle_id')}")
    print(f"goal            : {state.get('goal')}")
    print(f"status          : {state.get('status')}")
    print(f"loop_count      : {state.get('loop_count', 0)}")
    print(f"base_commit     : {state.get('base_commit') or '(none)'}")
    print(f"last_good_commit: {state.get('last_good_commit') or '(none)'}")
    if state.get("stop_reason"):
        print(f"stop_reason     : {state['stop_reason']}")
    ng_hist = state.get("ng_history", [])
    if ng_hist:
        print(f"ng_history ({len(ng_hist)}):")
        for h in ng_hist:
            print(f"  {h['timestamp']}  {h['reason']}")
    loops = state.get("loops", [])
    if loops:
        print("loops:")
        for lp in loops:
            print(f"  [{lp['loop_id']}] {lp['timestamp']}  test={lp['test_result']}"
                  f"  pre={lp.get('pre_commit','?')}→{lp['commit']}  {lp['summary']}")
    return 0


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="cycle state manager")
    sub = parser.add_subparsers(dest="cmd")

    p_start = sub.add_parser("start")
    p_start.add_argument("--goal", required=True)

    p_record = sub.add_parser("record")
    p_record.add_argument("--commit", default="")
    p_record.add_argument("--files", nargs="*", default=[])
    p_record.add_argument("--test", choices=["pass", "fail", "skip"], required=True)
    p_record.add_argument("--summary", default="")

    sub.add_parser("submit")

    sub.add_parser("approve")

    p_reject = sub.add_parser("reject")
    p_reject.add_argument("--reason", default="")

    p_ng = sub.add_parser("ng")
    p_ng.add_argument("--reason", default="")

    p_stop = sub.add_parser("stop")
    p_stop.add_argument("--reason", default="")

    sub.add_parser("done")
    sub.add_parser("status")

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        sys.exit(1)

    dispatch = {
        "start": cmd_start,
        "record": cmd_record,
        "submit": cmd_submit,
        "approve": cmd_approve,
        "reject": cmd_reject,
        "ng": cmd_ng,
        "done": cmd_done,
        "stop": cmd_stop,
        "status": cmd_status,
    }
    sys.exit(dispatch[args.cmd](args))


if __name__ == "__main__":
    main()
