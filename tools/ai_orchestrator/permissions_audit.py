# tools/ai_orchestrator/permissions_audit.py
"""
.claude/settings.local.json の検証・集計 CLI。

承認ダイアログ削減のため、ad hoc な python -c や && 連結の代替として使う。

usage:
    python -m tools.ai_orchestrator.permissions_audit validate-settings
    python -m tools.ai_orchestrator.permissions_audit summarize-settings
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SETTINGS_PATH = REPO_ROOT / ".claude" / "settings.local.json"


def cmd_validate(args: argparse.Namespace) -> int:
    path = Path(args.path) if args.path else SETTINGS_PATH
    if not path.exists():
        print(f"[ERROR] ファイルが見つかりません: {path}")
        return 1
    try:
        json.loads(path.read_text(encoding="utf-8"))
        print(f"[OK] JSON valid: {path}")
        return 0
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON invalid: {e}")
        return 1


def cmd_summarize(args: argparse.Namespace) -> int:
    path = Path(args.path) if args.path else SETTINGS_PATH
    if not path.exists():
        print(f"[ERROR] ファイルが見つかりません: {path}")
        return 1
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON invalid: {e}")
        return 1

    p = data.get("permissions", {})
    print(f"defaultMode : {p.get('defaultMode', '(未設定)')}")
    print(f"allow       : {len(p.get('allow', []))} 件")
    print(f"ask         : {len(p.get('ask', []))} 件")
    print(f"deny        : {len(p.get('deny', []))} 件")
    return 0


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="permissions_audit")
    parser.add_argument("--path", default="", help="設定ファイルパス（省略時は .claude/settings.local.json）")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("validate-settings", help="JSON 妥当性確認")
    sub.add_parser("summarize-settings", help="allow/ask/deny 件数表示")

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        sys.exit(1)

    dispatch = {
        "validate-settings": cmd_validate,
        "summarize-settings": cmd_summarize,
    }
    sys.exit(dispatch[args.cmd](args))


if __name__ == "__main__":
    main()
