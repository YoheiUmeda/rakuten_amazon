# tools/ai_orchestrator/cycle_to_review_request.py
"""
cycle_state.json → review_request.json 変換 CLI。

status が pending_review のときのみ生成を許可する。
生成した JSON は既存の orchestrator.py がそのまま読める形式に合わせる。

usage:
    python -m tools.ai_orchestrator.cycle_to_review_request
    python -m tools.ai_orchestrator.cycle_to_review_request \\
        --test-cmd "venv/Scripts/python -m pytest tests/ -q" \\
        --output .ai/handoff/review_request.json
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from tools.ai_orchestrator.cycle_manager import REPO_ROOT, load_state

DEFAULT_OUTPUT = REPO_ROOT / ".ai" / "handoff" / "review_request.json"


def _git_diff(base_commit: str) -> str:
    """base_commit..HEAD の diff を返す。失敗時は空文字。"""
    if not base_commit:
        return ""
    try:
        r = subprocess.run(
            ["git", "diff", f"{base_commit}..HEAD"],
            capture_output=True, text=True, encoding="utf-8", cwd=REPO_ROOT,
        )
        return r.stdout if r.returncode == 0 else ""
    except Exception:
        return ""


def build_review_request(state: dict, test_cmd: str = "", test_output: str = "") -> dict:
    task = state.get("goal", "")
    loops = state.get("loops", [])

    seen: set[str] = set()
    changed_files: list[str] = []
    for lp in loops:
        for f in lp.get("changed_files", []):
            if f not in seen:
                changed_files.append(f)
                seen.add(f)

    return {
        "task": task,
        "changed_files": changed_files,
        "git_diff": _git_diff(state.get("base_commit", "")),
        **({"test_command": test_cmd} if test_cmd else {}),
        **({"test_output": test_output} if test_output else {}),
    }


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="cycle_state.json → review_request.json 変換（pending_review のみ）"
    )
    parser.add_argument("--test-cmd", default="", help="テストコマンド（任意）")
    parser.add_argument("--test-output", default="", help="テスト出力（任意）")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="出力先 JSON パス")
    args = parser.parse_args()

    # ── state 読み込み ────────────────────────────────────────────────────
    state = load_state()
    if not state:
        print("[ERROR] cycle_state.json が見つかりません。先に cycle_manager start を実行してください")
        sys.exit(1)

    # ── status チェック ───────────────────────────────────────────────────
    status = state.get("status")
    if status != "pending_review":
        print(f"[ERROR] status={status!r} です。review_request.json を生成できるのは pending_review のときだけです")
        print("  submit を先に実行してください: python -m tools.ai_orchestrator.cycle_manager submit")
        sys.exit(1)

    # ── 必須内容チェック ──────────────────────────────────────────────────
    task = state.get("goal", "")
    if not task:
        print("[ERROR] goal が空です。review_request.json を生成できません")
        sys.exit(1)

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
        sys.exit(1)

    # ── 変換・出力 ────────────────────────────────────────────────────────
    data = build_review_request(state, test_cmd=args.test_cmd, test_output=args.test_output)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"[OK] 出力: {output_path}")
    print(f"     task: {data['task'][:80]}")
    print(f"     changed_files ({len(data['changed_files'])}): {', '.join(data['changed_files'])}")
    print(f"     git_diff: {len(data['git_diff'])} chars")


if __name__ == "__main__":
    main()
