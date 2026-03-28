# tools/ai_orchestrator/generate_review_request.py
"""
git diff / staged files / テスト結果から review_request.json の下書きを生成する CLI。

usage:
    # staged 変更の下書き（dry-run で確認）
    python -m tools.ai_orchestrator.generate_review_request \
        --task "タスク説明" --staged --dry-run

    # 特定ファイルを指定してファイル生成
    python -m tools.ai_orchestrator.generate_review_request \
        --task "タスク説明" \
        --files rakuten_client.py price_calculation.py \
        --test-cmd "venv/Scripts/python -m pytest tests/ -v" \
        --run-tests \
        --open-questions "+3 の根拠は？" "byte_limit=800 は仕様か？" \
        --constraints "pass_filter に触れない" \
        --output .ai/handoff/review_request.json
"""
from __future__ import annotations

import argparse
import json
import locale
import os
import subprocess
import sys
from pathlib import Path

from tools.ai_orchestrator.openai_client import DEFAULT_MODEL

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = REPO_ROOT / ".ai" / "handoff" / "review_request.json"
DIFF_LINE_LIMIT = 1000
PER_FILE_LINE_LIMIT = 200
RELATED_CODE_CHAR_LIMIT = 4000


# ──────────────────────────────────────────────────────────────────────────
# git helpers
# ──────────────────────────────────────────────────────────────────────────

def _git(args: list[str]) -> str:
    result = subprocess.run(
        ["git"] + args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=REPO_ROOT,
    )
    if result.returncode != 0 and result.stderr:
        print(f"[WARN] git コマンド失敗 ({result.returncode}): {result.stderr.strip()}", file=sys.stderr)
    return result.stdout.strip()


def get_changed_files(staged: bool, files: list[str]) -> list[str]:
    """変更ファイル一覧を返す。--files 指定があればそれを優先。"""
    if files:
        return files
    ref = "--cached" if staged else "HEAD"
    out = _git(["diff", ref, "--name-only"])
    return [f for f in out.splitlines() if f]


def get_git_diff(staged: bool, files: list[str]) -> str:
    """git diff テキストを返す。1000行超は切り捨て。"""
    ref = "--cached" if staged else "HEAD"
    cmd = ["diff", ref, "--"] + files if files else ["diff", ref]
    out = _git(cmd)
    lines = out.splitlines()
    if len(lines) > DIFF_LINE_LIMIT:
        out = "\n".join(lines[:DIFF_LINE_LIMIT])
        out += f"\n\n[TRUNCATED: {len(lines)} lines total, showing first {DIFF_LINE_LIMIT}]"
    return out


# ──────────────────────────────────────────────────────────────────────────
# related code collector
# ──────────────────────────────────────────────────────────────────────────

def collect_related_code(
    files: list[str],
    per_file_lines: int = PER_FILE_LINE_LIMIT,
    total_chars: int = RELATED_CODE_CHAR_LIMIT,
) -> str:
    """指定ファイルの内容を結合して related_code 文字列を返す。行数・文字数で切り捨て。"""
    parts = []
    for f in files:
        path = REPO_ROOT / f
        if not path.exists():
            print(f"[WARN] --related-code: ファイルが見つかりません: {f}", file=sys.stderr)
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()
        if len(lines) > per_file_lines:
            content = "\n".join(lines[:per_file_lines])
            content += f"\n# [TRUNCATED: {len(lines)} lines, showing first {per_file_lines}]"
        parts.append(f"# --- {f} ---\n{content}")
    combined = "\n\n".join(parts)
    if len(combined) > total_chars:
        combined = combined[:total_chars]
        combined += f"\n# [TRUNCATED: total chars exceeded {total_chars}]"
    return combined


# ──────────────────────────────────────────────────────────────────────────
# test runner
# ──────────────────────────────────────────────────────────────────────────

def run_test_command(cmd: str) -> str:
    """テストコマンドを実行して stdout+stderr を返す。タイムアウト時は [TIMEOUT] を返す。"""
    print(f"[INFO] テスト実行: {cmd}")
    enc = locale.getpreferredencoding(False)  # Win: cp932 / Linux・Mac: utf-8
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            encoding=enc,
            errors="replace",
            cwd=REPO_ROOT,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        print("[WARN] テストコマンドがタイムアウトしました（300s）", file=sys.stderr)
        return "[TIMEOUT] テストコマンドが 300 秒以内に完了しませんでした"
    output = ((result.stdout or "") + (result.stderr or "")).strip()
    return output


# ──────────────────────────────────────────────────────────────────────────
# build / output
# ──────────────────────────────────────────────────────────────────────────

def build_review_request(
    task: str,
    changed_files: list[str],
    git_diff: str,
    test_command: str,
    test_output: str,
    related_code: str,
    open_questions: list[str],
    constraints: list[str],
    model: str = "",
) -> dict:
    data: dict = {"task": task, "changed_files": changed_files}
    if model:
        data["model"] = model
    if git_diff:
        data["git_diff"] = git_diff
    if test_command:
        data["test_command"] = test_command
    if test_output:
        data["test_output"] = test_output
    if related_code:
        data["related_code"] = related_code
    if open_questions:
        data["open_questions"] = open_questions
    if constraints:
        data["constraints"] = constraints
    return data


# ──────────────────────────────────────────────────────────────────────────
# main
# ──────────────────────────────────────────────────────────────────────────

def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="review_request.json の下書きを生成する"
    )
    parser.add_argument("--task", required=True, help="レビュー依頼タスクの説明")
    parser.add_argument("--files", nargs="*", default=[], help="対象ファイル（省略時は git diff から自動取得）")
    parser.add_argument("--staged", action="store_true", help="git diff --cached を使う（staged 変更）")
    parser.add_argument("--test-cmd", default="", help="テストコマンド（例: venv/Scripts/python -m pytest tests/ -v）")
    parser.add_argument("--run-tests", action="store_true", help="--test-cmd を実際に実行してテスト出力を取り込む")
    parser.add_argument("--related-code", nargs="*", default=[], metavar="F", help="関連コードファイル（内容を取り込む、複数可）")
    parser.add_argument("--open-questions", nargs="*", default=[], metavar="Q", help="未解決の疑問点（複数可）")
    parser.add_argument("--constraints", nargs="*", default=[], metavar="C", help="守るべき制約（複数可）")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="出力先 JSON パス")
    parser.add_argument("--dry-run", action="store_true", help="stdout に出力のみ、ファイル書き込みなし")
    parser.add_argument("--model", default=None,
                        help="使用モデル（省略時: OPENAI_MODEL env → gpt-4o-mini）")
    args = parser.parse_args()

    # 0. model 解決
    model = args.model or os.getenv("OPENAI_MODEL", DEFAULT_MODEL)

    # 1. changed files
    changed_files = get_changed_files(args.staged, args.files)
    if not changed_files:
        print("[WARN] 変更ファイルが見つかりません。--files で明示指定してください。", file=sys.stderr)

    # 2. git diff
    git_diff = get_git_diff(args.staged, changed_files)
    if not git_diff:
        print("[WARN] git diff が空です。ファイルが変更されているか確認してください。", file=sys.stderr)

    # 3. test output
    test_output = ""
    if args.run_tests and args.test_cmd:
        test_output = run_test_command(args.test_cmd)

    # 4. related code
    related_code = collect_related_code(getattr(args, "related_code", []))

    # 5. build
    data = build_review_request(
        task=args.task,
        changed_files=changed_files,
        git_diff=git_diff,
        test_command=args.test_cmd,
        test_output=test_output,
        related_code=related_code,
        open_questions=args.open_questions,
        constraints=args.constraints,
        model=model,
    )

    json_text = json.dumps(data, ensure_ascii=False, indent=2)

    if args.dry_run:
        print("\n[DRY-RUN] --- review_request.json (preview) ---")
        print(json_text)
        print(f"\n[DRY-RUN] 変更ファイル数: {len(changed_files)}")
        print("[DRY-RUN] ファイル書き込みはスキップしました。")
        return

    # 5. write
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json_text, encoding="utf-8")
    print(f"[OK] 出力: {output_path}")
    print(f"[INFO] task: {args.task[:80]}")
    print(f"[INFO] 変更ファイル数: {len(changed_files)}")
    print()
    print("次のコマンドでレビューを実行:")
    print(f"  venv/Scripts/python -m tools.ai_orchestrator.orchestrator "
          f"--input {output_path} --output docs/review_reply.md")


if __name__ == "__main__":
    main()
