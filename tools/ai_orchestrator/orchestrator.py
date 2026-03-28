# tools/ai_orchestrator/orchestrator.py
"""
review_request.json を読み込み、OpenAI Responses API でレビューを実行し
review_reply.md を出力する CLI。

usage:
    # dry-run（openai 不要・API キー不要）
    python -m tools.ai_orchestrator.orchestrator \\
        --input .ai/handoff/review_request.example.json \\
        --output docs/review_reply.md \\
        --dry-run

    # 実行（openai インストール済み・OPENAI_API_KEY 設定済み）
    python -m tools.ai_orchestrator.orchestrator \\
        --input .ai/handoff/review_request.json \\
        --output docs/review_reply.md
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from tools.ai_orchestrator.redaction import redact_dict_fields

REPO_ROOT = Path(__file__).resolve().parents[2]
SYSTEM_PROMPT_PATH = REPO_ROOT / ".ai" / "prompts" / "review_system.md"

# redact を適用するフィールド
REDACT_FIELDS = ["git_diff", "related_code", "test_output"]


# ──────────────────────────────────────────────────────────────────────────
# Validation
# ──────────────────────────────────────────────────────────────────────────

def validate_input(data: dict) -> None:
    """必須フィールドの存在と型を検証する（stdlib のみ）。"""
    required = ["task", "changed_files"]
    for key in required:
        if key not in data:
            raise ValueError(f"review_request に必須フィールドがありません: '{key}'")
    if not isinstance(data["changed_files"], list):
        raise ValueError("'changed_files' は配列でなければなりません")
    if not isinstance(data["task"], str) or not data["task"].strip():
        raise ValueError("'task' は空でない文字列でなければなりません")


# ──────────────────────────────────────────────────────────────────────────
# Prompt building
# ──────────────────────────────────────────────────────────────────────────

def build_user_content(data: dict) -> str:
    """review_request の dict からレビュー依頼テキストを組み立てる。"""
    lines: list[str] = []

    lines.append(f"## タスク\n{data['task']}\n")

    files = data.get("changed_files", [])
    if files:
        lines.append("## 変更ファイル\n" + "\n".join(f"- {f}" for f in files) + "\n")

    if data.get("git_diff"):
        lines.append(f"## git diff\n```diff\n{data['git_diff']}\n```\n")

    if data.get("test_command"):
        lines.append(f"## テストコマンド\n`{data['test_command']}`\n")

    if data.get("test_output"):
        lines.append(f"## テスト出力\n```\n{data['test_output']}\n```\n")

    if data.get("related_code"):
        lines.append(f"## 関連コード\n```python\n{data['related_code']}\n```\n")

    questions = data.get("open_questions", [])
    if questions:
        lines.append("## 未解決の疑問点\n" + "\n".join(f"- {q}" for q in questions) + "\n")

    constraints = data.get("constraints", [])
    if constraints:
        lines.append("## 守るべき制約\n" + "\n".join(f"- {c}" for c in constraints) + "\n")

    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────
# Main flow
# ──────────────────────────────────────────────────────────────────────────

def run(input_path: Path, output_path: Path, dry_run: bool) -> None:
    # 1. input JSON 読み込み
    if not input_path.exists():
        print(f"[ERROR] 入力ファイルが見つかりません: {input_path}", file=sys.stderr)
        sys.exit(1)

    raw = input_path.read_text(encoding="utf-8")
    try:
        data: dict = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON パース失敗: {e}", file=sys.stderr)
        sys.exit(1)

    # 2. 検証
    try:
        validate_input(data)
    except ValueError as e:
        print(f"[ERROR] 入力検証失敗: {e}", file=sys.stderr)
        sys.exit(1)

    # 3. redaction
    data = redact_dict_fields(data, REDACT_FIELDS)

    # 4. system prompt 読み込み
    if not SYSTEM_PROMPT_PATH.exists():
        print(f"[ERROR] system prompt が見つかりません: {SYSTEM_PROMPT_PATH}", file=sys.stderr)
        sys.exit(1)
    system_prompt = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")

    # 5. user content 組み立て
    user_content = build_user_content(data)

    print(f"[INFO] 入力: {input_path}")
    task_preview = data["task"][:80]
    suffix = "..." if len(data["task"]) > 80 else ""
    print(f"[INFO] タスク: {task_preview}{suffix}")
    print(f"[INFO] 変更ファイル数: {len(data.get('changed_files', []))}")

    if dry_run:
        # dry-run: API を呼ばず、整形内容を stdout に出力
        print("\n[DRY-RUN] --- system prompt (先頭200字) ---")
        print(system_prompt[:200])
        print("\n[DRY-RUN] --- user content ---")
        print(user_content)
        print("\n[DRY-RUN] 完了。API 呼び出しはスキップしました。")
        return

    # 6. OpenAI API 呼び出し
    from tools.ai_orchestrator.openai_client import call_review

    try:
        reply_text = call_review(system_prompt=system_prompt, user_content=user_content)
    except (ImportError, ValueError) as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    # 7. 出力
    header = (
        f"# Review Reply\n\n"
        f"生成日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"入力: `{input_path}`\n\n---\n\n"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(header + reply_text, encoding="utf-8")
    print(f"[OK] 出力: {output_path}")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    load_dotenv(override=True)

    parser = argparse.ArgumentParser(
        description="review_request.json → review_reply.md を生成する"
    )
    parser.add_argument("--input",   required=True, help="review_request.json のパス")
    parser.add_argument("--output",  required=True, help="review_reply.md の出力先")
    parser.add_argument("--dry-run", action="store_true", help="API を呼ばず入力確認のみ")
    args = parser.parse_args()

    run(
        input_path=Path(args.input),
        output_path=Path(args.output),
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
