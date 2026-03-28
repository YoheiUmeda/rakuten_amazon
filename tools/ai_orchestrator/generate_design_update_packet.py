# tools/ai_orchestrator/generate_design_update_packet.py
"""
設計書更新パケット (docs/design_update_packet.md) を生成する CLI。

usage:
    # ステージング済みファイルをもとに生成
    python -m tools.ai_orchestrator.generate_design_update_packet --staged

    # 直前のコミットとの差分をもとに生成
    python -m tools.ai_orchestrator.generate_design_update_packet --since HEAD~1

    # サンプル入力で dry-run（git 不要）
    python -m tools.ai_orchestrator.generate_design_update_packet --dry-run
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from tools.ai_orchestrator.design_doc_mapper import (
    DOC_LABELS,
    DOC_PATHS,
    map_changed_files,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_PATH = REPO_ROOT / "docs" / "templates" / "design_update_packet.md"
OUTPUT_PATH = REPO_ROOT / "docs" / "design_update_packet.md"

# --dry-run 時に使うサンプルファイルリスト
DRY_RUN_SAMPLE = [
    "app/api/prices.py",
    "app/schemas.py",
    "batch_runner.py",
    "rakuten_client.py",
]


def get_changed_files(mode: str) -> list[str]:
    if mode == "staged":
        cmd = ["git", "diff", "--name-only", "--cached"]
    else:
        cmd = ["git", "diff", "--name-only", mode]

    result = subprocess.run(
        cmd, capture_output=True, text=True, cwd=REPO_ROOT
    )
    if result.returncode != 0:
        print(f"[ERROR] git コマンド失敗: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)

    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def get_diff_summary(mode: str) -> str:
    if mode == "staged":
        cmd = ["git", "diff", "--stat", "--cached"]
    else:
        cmd = ["git", "diff", "--stat", mode]

    result = subprocess.run(
        cmd, capture_output=True, text=True, cwd=REPO_ROOT
    )
    return result.stdout.strip() or "(差分なし)"


def get_branch() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    return result.stdout.strip() or "unknown"


def build_candidate_rows(mapping: dict[str, list[str]]) -> str:
    if not mapping:
        return "| (更新対象なし) | — | — | — | — |"
    rows = []
    later = {"data_model", "ui_design", "functional_requirements"}
    for doc_id, files in sorted(mapping.items()):
        label = DOC_LABELS.get(doc_id, doc_id)
        path = DOC_PATHS.get(doc_id, "—")
        reason = ", ".join(files)
        priority = "後回し可" if doc_id in later else "要確認"
        target = REPO_ROOT / path
        exists = target.exists()
        status = "既存" if exists else "未作成"
        rows.append(f"| {label} | `{path}` | {status} | {reason} | {priority} |")
    return "\n".join(rows)


def build_changed_files_text(files: list[str]) -> str:
    if not files:
        return "(変更ファイルなし)"
    return "\n".join(f"- `{f}`" for f in files)


def generate(mode: str, dry_run: bool) -> None:
    if dry_run:
        changed_files = DRY_RUN_SAMPLE
        diff_summary = "(dry-run: サンプル入力)"
        branch = "main (dry-run)"
        diff_range = "dry-run"
    else:
        changed_files = get_changed_files(mode)
        diff_summary = get_diff_summary(mode)
        branch = get_branch()
        diff_range = "staged" if mode == "staged" else mode

    mapping = map_changed_files(changed_files)

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    content = template.format(
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        branch=branch,
        diff_range=diff_range,
        changed_files=build_changed_files_text(changed_files),
        candidate_rows=build_candidate_rows(mapping),
        diff_summary=diff_summary,
    )

    OUTPUT_PATH.write_text(content, encoding="utf-8")
    print(f"[OK] 生成完了: {OUTPUT_PATH}")
    print(f"     変更ファイル数: {len(changed_files)}")
    print(f"     更新候補設計書数: {len(mapping)}")
    for doc_id, files in sorted(mapping.items()):
        label = DOC_LABELS.get(doc_id, doc_id)
        print(f"     - {label} ({DOC_PATHS.get(doc_id, '?')}): {files}")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="設計書更新パケット (design_update_packet.md) を生成する"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--staged", action="store_true", help="ステージング済み差分を使用")
    group.add_argument("--since", metavar="REF", help="指定コミット以降の差分 (例: HEAD~1)")
    group.add_argument("--dry-run", action="store_true", help="サンプル入力で動作確認")
    args = parser.parse_args()

    if args.dry_run:
        generate(mode="staged", dry_run=True)
    elif args.staged:
        generate(mode="staged", dry_run=False)
    elif args.since:
        generate(mode=args.since, dry_run=False)
    else:
        generate(mode="staged", dry_run=False)


if __name__ == "__main__":
    main()
