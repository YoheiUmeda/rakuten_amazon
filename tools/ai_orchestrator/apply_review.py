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
import subprocess
import sys
from pathlib import Path

from tools.ai_orchestrator.generate_review_request import REPO_ROOT

REVIEW_REPLY_MD = REPO_ROOT / "docs" / "handoff" / "review_reply.md"
RESULT_MD = REPO_ROOT / "docs" / "handoff" / "result.md"
TASK_MD = REPO_ROOT / "docs" / "handoff" / "task.md"
ARCHIVE_DIR = REPO_ROOT / "docs" / "handoff" / "archive"


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


def _archive_task(task_path: Path, archive_dir: Path) -> bool:
    """task.md の status を done に更新して archive へ移動する。fail-open で False を返す。

    abort 条件:
    - task.md が存在しない
    - task_id が空
    - 移動先ファイルが既に存在する
    """
    if not task_path.exists():
        print("[WARN] task.md が見つかりません。archive をスキップします。")
        return False

    text = task_path.read_text(encoding="utf-8")

    m_id = re.search(r'^task_id:\s*["\']?([^"\'#\n]+)["\']?', text, re.MULTILINE)
    task_id = m_id.group(1).strip() if m_id else ""
    if not task_id:
        print("[WARN] task_id が空です。archive をスキップします。")
        return False

    m_slug = re.search(r'^slug:\s*["\']?([^"\'#\n]+)["\']?', text, re.MULTILINE)
    slug = m_slug.group(1).strip() if m_slug else ""

    m_date = re.search(r'^updated:\s*([^\s#\n]+)', text, re.MULTILINE)
    date_str = (m_date.group(1).strip() if m_date else "").replace("-", "")

    fname = f"{date_str}_task_{task_id}"
    if slug:
        fname += f"_{slug}"
    fname += ".md"

    dest = archive_dir / fname
    if dest.exists():
        print(f"[WARN] archive 先が既に存在します: {dest}。archive をスキップします。")
        return False

    updated_text = re.sub(
        r'^(status:\s*)(?:draft|pending|approved|done)',
        r'\g<1>done',
        text, count=1, flags=re.MULTILINE,
    )

    archive_dir.mkdir(parents=True, exist_ok=True)
    task_path.write_text(updated_text, encoding="utf-8")
    task_path.rename(dest)
    return True


def _extract_reject_reason(reply_text: str) -> str:
    """review_reply.md から reject 理由を抽出する。

    優先順: Required changes の先頭箇条書き → Issues の先頭箇条書き → デフォルト文字列
    """
    for section in ("Required changes", "Issues"):
        body = _parse_section(reply_text, section)
        for line in body.splitlines():
            stripped = line.strip()
            if stripped.startswith("- ") and stripped[2:].strip():
                return stripped[2:].strip()
    return "request_changes by AI review"


def _run_cycle_approve() -> bool:
    """cycle_manager approve をサブプロセスで実行する。成功なら True（fail-open）。"""
    try:
        r = subprocess.run(
            [sys.executable, "-m", "tools.ai_orchestrator.cycle_manager", "approve"],
            cwd=REPO_ROOT,
        )
        return r.returncode == 0
    except Exception:
        return False


def _run_cycle_reject(reason: str) -> bool:
    """cycle_manager reject をサブプロセスで実行する。成功なら True（fail-open）。"""
    try:
        r = subprocess.run(
            [sys.executable, "-m", "tools.ai_orchestrator.cycle_manager", "reject",
             "--reason", reason],
            cwd=REPO_ROOT,
        )
        return r.returncode == 0
    except Exception:
        return False


def apply_review(
    reply_path: Path = REVIEW_REPLY_MD,
    result_path: Path = RESULT_MD,
    dry_run: bool = False,
    auto_approve: bool = False,
    auto_archive: bool = False,
    auto_reject: bool = False,
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
        cycle_approved = False
        if auto_approve and not dry_run:
            if _run_cycle_approve():
                print("[OK] cycle_manager approve 完了")
                cycle_approved = True
            else:
                print("[WARN] cycle_manager approve 失敗")
                print("       result.md は更新済み / cycle は未確定 / task.md は未移動")
                print("       手動で実行: venv/Scripts/python -m tools.ai_orchestrator.cycle_manager approve")
        if auto_archive and not dry_run:
            if not auto_approve:
                print("[WARN] --auto-archive は --auto-approve と同時に使用してください。archive をスキップします。")
            elif not cycle_approved:
                print("[WARN] cycle_manager approve が未完了のため、task.md の archive をスキップします。")
            else:
                if _archive_task(TASK_MD, ARCHIVE_DIR):
                    print("[OK] task.md を archive へ移動しました")
                else:
                    print("[WARN] task.md の archive 失敗（手動で移動してください）")
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
        if auto_reject and not dry_run:
            reason = _extract_reject_reason(reply_text)
            if _run_cycle_reject(reason):
                print(f"[OK] cycle_manager reject 完了 (reason: {reason[:80]})")
            else:
                print("[WARN] cycle_manager reject 失敗")
                print(f"       手動で実行: venv/Scripts/python -m tools.ai_orchestrator.cycle_manager reject --reason \"{reason}\"")
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
    parser.add_argument("--auto-approve", action="store_true", dest="auto_approve",
                        help="Approve 時に cycle_manager approve を自動実行（opt-in）")
    parser.add_argument("--auto-archive", action="store_true", dest="auto_archive",
                        help="Approve 時に task.md を done に更新して archive へ移動（opt-in）")
    parser.add_argument("--auto-reject", action="store_true", dest="auto_reject",
                        help="Request changes 時に cycle_manager reject を自動実行（opt-in）")
    args = parser.parse_args()

    sys.exit(apply_review(Path(args.reply), Path(args.result), args.dry_run, args.auto_approve, args.auto_archive, args.auto_reject))


if __name__ == "__main__":
    main()
