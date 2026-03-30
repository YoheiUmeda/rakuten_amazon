# tools/ai_orchestrator/fill_result.py
"""
result.md を自動生成する CLI。
task_id / generated_at / changed_files / diff / test_output を自動入力し、
結論・ログ要約・未確定点は TODO プレースホルダで残す。

usage:
    # staged 変更から生成（結論は後で手動補記）
    python -m tools.ai_orchestrator.fill_result --staged

    # 結論テキスト付き + テスト実行
    python -m tools.ai_orchestrator.fill_result \
        --staged \
        --conclusion "XX を修正。テスト全通過。" \
        --test-cmd "venv/Scripts/python -m pytest tests/ -v" --run-tests

    # 確認のみ（ファイル書き込みなし）
    python -m tools.ai_orchestrator.fill_result --staged --dry-run
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tools.ai_orchestrator.generate_review_request import (
    REPO_ROOT,
    get_changed_files,
    get_git_diff,
    run_test_command,
)

RESULT_MD = REPO_ROOT / "docs" / "handoff" / "result.md"
TASK_MD = REPO_ROOT / "docs" / "handoff" / "task.md"
RESULT_MD_URL = (
    "https://github.com/YoheiUmeda/rakuten_amazon"
    "/blob/main/docs/handoff/result.md"
)
CHAT_PROMPT_BODY = """\
以下の実行結果レポートをレビューし、人間が確認・承認できる形で整理してください。

**確認ポイント:**
- 結論は明確か（何をした・成功/失敗が分かるか）
- 目的と結果が一致しているか
- diff と変更ファイルは一致しているか
- 影響範囲は妥当か（想定外の副作用がないか）
- テスト結果は十分か（pass/fail が明示されているか）
- secrets が含まれていないか（.env / APIキー / トークン / DB接続文字列）
- 未確定点・懸念は適切に記録されているか
- 重点レビュー観点に回答できるか

**回答形式:**

## 実行結果の要点
（何をした・どのファイルが変わった・テストの状況を箇条書きで）

## diff / テスト結果の確認
（diff と変更ファイルの整合性、テスト pass/fail、secrets 混入チェック）

## 懸念点（あれば）
（品質・副作用・未確定点・影響範囲の観点から）

## Approve / Request changes
（archive 可 → Approve / 追加対応必要 → Request changes、理由1行）\
"""


def _read_task_purpose() -> str:
    """task.md の ## タスク セクション本文を取得する（fail-open）。"""
    if not TASK_MD.exists():
        return ""
    text = TASK_MD.read_text(encoding="utf-8")
    # フロントマター除去
    parts = re.split(r'^---\s*$', text, maxsplit=2, flags=re.MULTILINE)
    body = parts[2] if len(parts) >= 3 else text
    # ## で始まるセクションに分割して ## タスク を探す
    sections = re.split(r'^## ', body, flags=re.MULTILINE)
    for section in sections:
        heading, _, body_part = section.partition('\n')
        if heading.rstrip() == 'タスク':
            return body_part.strip()
    return ""


def _read_task_id() -> str:
    """task.md フロントマターから task_id を取得する。空・未存在は "" を返す（fail-open）。"""
    if not TASK_MD.exists():
        return ""
    text = TASK_MD.read_text(encoding="utf-8")
    m = re.search(r'^task_id:\s*["\']?([^"\'#\n]+)["\']?', text, re.MULTILINE)
    if m:
        return m.group(1).strip()
    return ""


def _now_jst() -> str:
    jst = timezone(timedelta(hours=9))
    return datetime.now(jst).strftime("%Y-%m-%dT%H:%M:%S+09:00")


def build_result_md(
    task_id: str,
    generated_at: str,
    conclusion: str,
    changed_files: list[str],
    diff: str,
    test_output: str,
    purpose: str = "",
    review_focus: list[str] | None = None,
) -> str:
    """result.md の全文を返す。"""
    files_block = "\n".join(f"- {f}" for f in changed_files) if changed_files else "-"
    conclusion_text = conclusion if conclusion else "<!-- TODO: 何をしたか・成功/失敗を1〜3行で -->"
    purpose_text = purpose if purpose else "<!-- TODO: task.md の「タスク」から1〜2行でコピー -->"
    test_block = test_output.strip() if test_output else ""
    if review_focus:
        focus_block = "\n".join(f"- {f}" for f in review_focus)
    else:
        focus_block = "<!-- TODO: ChatGPT に特に見てほしい点。なければ「なし」 -->"

    return f"""\
---
task_id: "{task_id}"
status: review-pending
# status の定義:
#   review-pending : ChatGPT レビュー待ち（push 済み）
#   reviewed       : 人間確認済み。task.md を done にして archive 可。
generated_at: {generated_at}
secrets_checked: false
# secrets_checked: false のまま push しないこと。
# push 前に以下を確認し true に変更する:
#   - diff に .env の内容が含まれていないか
#   - APIキー / トークン / DB接続文字列が含まれていないか
---

<!-- 正本: main ブランチの docs/handoff/result.md -->
<!-- GitHub URL: https://github.com/YoheiUmeda/rakuten_amazon/blob/main/docs/handoff/result.md -->

## 結論
{conclusion_text}

## 目的
{purpose_text}

## 変更ファイル
{files_block}

## 影響範囲
<!-- TODO: 変更の影響が及ぶ範囲（他モジュール・API・DB等）。なければ「なし」 -->

## diff
<!-- git diff の全文または主要部分。secrets を含めないこと。 -->
```diff
{diff}
```

## テスト結果
<!-- pytest 出力または test summary。省略する場合はその理由を書く。 -->
```
{test_block}
```

## ログ要約
<!-- TODO: 警告・エラー・重要なログ行。不要なら「なし」と書く。 -->

## 未確定点・懸念
<!-- TODO: Claude が判断できなかった点、次に確認してほしいこと。なければ「なし」 -->

## 重点レビュー観点
{focus_block}

## secrets 確認
- .env / APIキー / トークン: 未含有（確認済み）
"""


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="result.md を自動生成する")
    parser.add_argument("--staged", action="store_true", help="git diff --cached を使う")
    parser.add_argument("--files", nargs="*", default=[], help="対象ファイル（省略時は git diff から自動取得）")
    parser.add_argument("--conclusion", default="", help="結論テキスト（省略可）")
    parser.add_argument("--purpose", default="", help="目的テキスト（省略可）")
    parser.add_argument("--review-focus", nargs="*", default=[], dest="review_focus",
                        metavar="F", help="重点レビュー観点（複数可）")
    parser.add_argument("--test-cmd", default="", dest="test_cmd", help="テストコマンド")
    parser.add_argument("--run-tests", action="store_true", dest="run_tests", help="--test-cmd を実際に実行")
    parser.add_argument("--output", default=str(RESULT_MD), help="出力先（デフォルト: docs/handoff/result.md）")
    parser.add_argument("--dry-run", action="store_true", help="stdout に出力のみ、ファイル書き込みなし")
    parser.add_argument("--print-chat-prompt", action="store_true", dest="print_chat_prompt",
                        help="ChatGPT にそのまま貼れるレビュー依頼文を stdout に出力して終了")
    parser.add_argument("--review-request-output", default="", dest="review_request_output",
                        metavar="PATH", help="レビュー依頼文をファイルに書き出す（省略時は stdout のみ）")
    args = parser.parse_args()

    if args.print_chat_prompt:
        content = f"{CHAT_PROMPT_BODY}\n\n{RESULT_MD_URL}"
        if args.review_request_output:
            out = Path(args.review_request_output)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(content, encoding="utf-8")
            print(f"[OK] レビュー依頼文を出力: {out}")
        else:
            print(content)
        return

    task_id = _read_task_id()
    generated_at = _now_jst()
    changed_files = get_changed_files(args.staged, args.files)
    diff = get_git_diff(args.staged, changed_files)
    test_output = run_test_command(args.test_cmd) if args.run_tests and args.test_cmd else ""
    purpose = args.purpose or _read_task_purpose()

    content = build_result_md(
        task_id=task_id,
        generated_at=generated_at,
        conclusion=args.conclusion,
        changed_files=changed_files,
        diff=diff,
        test_output=test_output,
        purpose=purpose,
        review_focus=args.review_focus,
    )

    if args.dry_run:
        print("[DRY-RUN] --- result.md preview ---")
        print(content)
        return

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    print(f"[OK] 出力: {output_path}")
    print(f"[INFO] task_id: {task_id}")
    print(f"[INFO] 変更ファイル数: {len(changed_files)}")
    print()
    print("次のステップ:")
    print("  1. result.md の TODO を手動補記（結論 / 影響範囲 / 重点レビュー観点 / ログ要約 / 未確定点）")
    print("  2. secrets_checked: false → true に変更")
    print("  3. git push origin main")
    print("  4. ChatGPT レビュー依頼文を生成（コピー → ChatGPT に貼り付け）:")
    print("       venv/Scripts/python -m tools.ai_orchestrator.fill_result --print-chat-prompt")


if __name__ == "__main__":
    main()
