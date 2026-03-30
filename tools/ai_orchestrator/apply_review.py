# tools/ai_orchestrator/apply_review.py
"""
review_reply.md を読んで result.md を更新する CLI。

usage:
    python -m tools.ai_orchestrator.apply_review
    python -m tools.ai_orchestrator.apply_review --dry-run
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from tools.ai_orchestrator.generate_review_request import REPO_ROOT

REVIEW_REPLY_MD = REPO_ROOT / "docs" / "handoff" / "review_reply.md"
RESULT_MD = REPO_ROOT / "docs" / "handoff" / "result.md"


def _parse_section(text: str, heading: str) -> str:
    """## heading の本文を返す（次の ## まで）。なければ ''。"""
    sections = re.split(r'^## ', text, flags=re.MULTILINE)
    for section in sections:
        head, _, body = section.partition('\n')
        if head.rstrip() == heading:
            return body.strip()
    return ""


def _parse_decision(reply_text: str) -> str:
    """Decision セクションから 'approve' または 'request_changes' を返す。"""
    body = _parse_section(reply_text, "Decision").lower()
    if "approve" in body:
        return "approve"
    if "request" in body:
        return "request_changes"
    return ""


def apply_review(
    reply_path: Path = REVIEW_REPLY_MD,
    result_path: Path = RESULT_MD,
    dry_run: bool = False,
) -> int:
    """0: success, 1: error"""
    if not reply_path.exists():
        print(f"[ERROR] review_reply.md が見つかりません: {reply_path}", file=sys.stderr)
        return 1

    reply_text = reply_path.read_text(encoding="utf-8")
    decision = _parse_decision(reply_text)

    if not decision:
        print("[ERROR] ## Decision に Approve / Request changes が見つかりません", file=sys.stderr)
        return 1

    if decision == "approve":
        if not result_path.exists():
            print(f"[ERROR] result.md が見つかりません: {result_path}", file=sys.stderr)
            return 1
        result_text = result_path.read_text(encoding="utf-8")
        updated = result_text.replace("status: review-pending", "status: reviewed", 1)
        changed = updated != result_text
        if not changed:
            print("[WARN] status: review-pending が見つかりません。result.md は変更しません。")
        elif dry_run:
            print("[DRY-RUN] result.md を status: reviewed に更新します（変更なし）")
        else:
            result_path.write_text(updated, encoding="utf-8")
            print("[OK] result.md を status: reviewed に更新しました")
        print()
        print("Decision: Approve")
        print(f"Updated: {'result.md' if changed and not dry_run else 'none'}")
        print("Next: task.md の status を done にして archive へ移動する")
    else:
        issues = _parse_section(reply_text, "Issues")
        required = _parse_section(reply_text, "Required changes")
        if issues:
            print(f"## Issues\n{issues}\n")
        if required:
            print(f"## Required changes\n{required}\n")
        print("Decision: Request changes")
        print("Updated: none")
        print("Next: 上記の変更を実施後、再度 fill_result → レビュー依頼")
    return 0


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="review_reply.md を読んで result.md を更新する")
    parser.add_argument("--reply", default=str(REVIEW_REPLY_MD), help="review_reply.md のパス")
    parser.add_argument("--result", default=str(RESULT_MD), help="result.md のパス")
    parser.add_argument("--dry-run", action="store_true", help="ファイル変更なし")
    args = parser.parse_args()

    sys.exit(apply_review(Path(args.reply), Path(args.result), args.dry_run))


if __name__ == "__main__":
    main()
