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
TASK_MD_PATH = REPO_ROOT / "docs" / "handoff" / "task.md"
REVIEW_SUMMARY_PATH = REPO_ROOT / "docs" / "handoff" / "review_summary.md"


def _git_diff(base_commit: str) -> str:
    """base_commit..HEAD の diff を返す。空の場合は base_commit^..base_commit を試みる（fail-open）。"""
    if not base_commit:
        return ""
    try:
        r = subprocess.run(
            ["git", "diff", f"{base_commit}..HEAD"],
            capture_output=True, text=True, encoding="utf-8", cwd=REPO_ROOT,
        )
        diff = r.stdout if r.returncode == 0 else ""
        if diff:
            return diff
        # fallback: base_commit == HEAD のとき（start 後にコミット済みのケース）
        r2 = subprocess.run(
            ["git", "diff", f"{base_commit}^..{base_commit}"],
            capture_output=True, text=True, encoding="utf-8", cwd=REPO_ROOT,
        )
        return r2.stdout if r2.returncode == 0 else ""
    except Exception:
        return ""


def _extract_constraints(task_md_path: Path) -> list[str]:
    """task.md の「実施条件・制約」セクションの箇条書きを返す。ファイルがなければ空リスト。"""
    if not task_md_path.exists():
        return []
    try:
        text = task_md_path.read_text(encoding="utf-8")
    except Exception:
        return []
    in_section = False
    items: list[str] = []
    for line in text.splitlines():
        if line.strip().startswith("## 実施条件・制約"):
            in_section = True
            continue
        if in_section:
            if line.startswith("## "):
                break
            stripped = line.strip()
            if stripped.startswith("- ") and stripped[2:].strip():
                items.append(stripped[2:].strip())
    return items


def _extract_open_questions(ng_history: list[dict]) -> list[str]:
    """ng_history の reason を open_questions として返す。空なら空リスト。"""
    return [h["reason"] for h in ng_history if h.get("reason")]


def _extract_summary(review_summary_path: Path) -> str:
    """review_summary.md の「懸念点」セクション内容を返す。なければ空文字。"""
    if not review_summary_path.exists():
        return ""
    try:
        text = review_summary_path.read_text(encoding="utf-8")
    except Exception:
        return ""
    in_section = False
    lines: list[str] = []
    for line in text.splitlines():
        if line.strip().startswith("## 懸念点"):
            in_section = True
            continue
        if in_section:
            if line.startswith("## "):
                break
            lines.append(line)
    content = "\n".join(lines).strip()
    return "" if not content or content == "- なし" else content


def build_review_request(
    state: dict,
    test_cmd: str = "",
    test_output: str = "",
    task_md_path: Path | None = None,
    review_summary_path: Path | None = None,
) -> dict:
    task = state.get("goal", "")
    loops = state.get("loops", [])

    seen: set[str] = set()
    changed_files: list[str] = []
    for lp in loops:
        for f in lp.get("changed_files", []):
            if f not in seen:
                changed_files.append(f)
                seen.add(f)

    result: dict = {
        "task": task,
        "changed_files": changed_files,
        "git_diff": _git_diff(state.get("base_commit", "")),
    }
    if test_cmd:
        result["test_command"] = test_cmd
    if test_output:
        result["test_output"] = test_output

    constraints = _extract_constraints(task_md_path or TASK_MD_PATH)
    if constraints:
        result["constraints"] = constraints

    open_questions = _extract_open_questions(state.get("ng_history", []))
    if open_questions:
        result["open_questions"] = open_questions

    summary = _extract_summary(review_summary_path or REVIEW_SUMMARY_PATH)
    if summary:
        result["summary"] = summary

    return result


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
