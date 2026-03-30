# tools/ai_orchestrator/review_summary.py
"""
確認不要モード Phase 1: cycle_state.json からレビュー用 markdown を生成する CLI。

usage:
    python -m tools.ai_orchestrator.review_summary
    python -m tools.ai_orchestrator.review_summary --dry-run
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tools.ai_orchestrator.cycle_manager import load_state, SOFT_LIMIT

REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = REPO_ROOT / "docs" / "handoff" / "review_summary.md"


def _now_jst() -> str:
    jst = timezone(timedelta(hours=9))
    return datetime.now(jst).strftime("%Y-%m-%dT%H:%M:%S+09:00")


def build_summary(state: dict) -> str:
    goal = state.get("goal", "(未設定)")
    status = state.get("status", "unknown")
    loop_count = state.get("loop_count", 0)
    stop_reason = state.get("stop_reason") or "なし"
    loops = state.get("loops", [])

    # test 結果集計
    test_counts = {"pass": 0, "fail": 0, "skip": 0}
    for lp in loops:
        r = lp.get("test_result", "skip")
        test_counts[r] = test_counts.get(r, 0) + 1

    # 変更ファイル（全ループ分・重複除去）
    all_files: list[str] = []
    seen: set[str] = set()
    for lp in loops:
        for f in lp.get("changed_files", []):
            if f not in seen:
                all_files.append(f)
                seen.add(f)

    # NG 履歴
    ng_history = state.get("ng_history", [])

    # rollback 情報
    base_commit = state.get("base_commit") or "(none)"
    last_good_commit = state.get("last_good_commit") or "(none)"
    last_pre_commit = loops[-1].get("pre_commit", "(none)") if loops else "(none)"

    # 懸念点
    concerns: list[str] = []
    if test_counts["fail"] > 0:
        concerns.append(f"テスト失敗ループあり ({test_counts['fail']} 回)")
    if loop_count > SOFT_LIMIT:
        concerns.append(f"ループ数が多い ({loop_count} 回、推奨 {SOFT_LIMIT} 以下)")
    if status == "stopped":
        concerns.append(f"サイクルが停止しました: {stop_reason}")
    for h in ng_history:
        concerns.append(f"NG 指摘 [{h['timestamp'][:19]}]: {h['reason']}")

    # 次の判断（非エンジニア向け）
    if status == "done":
        next_action = "✅ 承認済み — 担当者が本番反映を実行します"
    elif status == "stopped":
        next_action = "⛔ 作業停止 — 担当者に原因と対応方針を確認してください"
    else:
        next_action = "⏳ 確認中 — OK の場合: 担当者に承認を伝えてください / NG の場合: 修正理由を担当者に伝えて再依頼してください"

    # ループ詳細
    loop_lines = []
    for lp in loops:
        files_str = ", ".join(lp.get("changed_files", [])) or "(なし)"
        loop_lines.append(
            f"| {lp['loop_id']} | {lp.get('timestamp','')[:19]} "
            f"| {lp.get('test_result','')} "
            f"| `{lp.get('commit','(none)')}` "
            f"| {files_str} "
            f"| {lp.get('summary','')} |"
        )
    loop_table = "\n".join(loop_lines) if loop_lines else "| - | - | - | - | - | (ループなし) |"

    concerns_text = "\n".join(f"- {c}" for c in concerns) if concerns else "- なし"
    files_text = "\n".join(f"- {f}" for f in all_files) if all_files else "- (なし)"

    return f"""\
<!-- review_summary generated_at: {_now_jst()} -->

# レビュー用ドキュメント

## 目的
{goal}

## サイクル情報
- cycle_id: `{state.get('cycle_id', '(none)')}`
- status: `{status}`
- ループ数: {loop_count}

## 変更ファイル（全ループ）
{files_text}

## ループ履歴
| # | 日時 | test | commit | 変更ファイル | 要約 |
|---|---|---|---|---|---|
{loop_table}

## テスト結果集計
- pass: {test_counts['pass']}
- fail: {test_counts['fail']}
- skip: {test_counts['skip']}

## rollback 情報（問題発生時に戻せる地点）
- サイクル開始前: `{base_commit}` （全変更を戻す場合）
- 最後にテスト通過: `{last_good_commit}` （直近の安全な状態）
- 直前ループ開始前: `{last_pre_commit}` （最後のループだけ戻す場合）

## 懸念点
{concerns_text}

## 次の判断
{next_action}
"""


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="cycle_state.json からレビュー用ドキュメントを生成する")
    parser.add_argument("--dry-run", action="store_true", help="stdout に出力のみ（ファイル書き込みなし）")
    args = parser.parse_args()

    state = load_state()
    if not state:
        print("[ERROR] cycle_state.json が見つかりません。先に cycle_manager start を実行してください",
              file=sys.stderr)
        sys.exit(1)

    content = build_summary(state)

    if args.dry_run:
        print("[DRY-RUN] --- review_summary preview ---")
        print(content)
        sys.exit(0)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(content, encoding="utf-8")
    print(f"[OK] 出力: {OUTPUT_PATH}")
    print(f"[INFO] status={state.get('status')}  loops={state.get('loop_count', 0)}")


if __name__ == "__main__":
    main()
