# tools/ai_orchestrator/review_reply_parser.py
"""review_reply.md から要点を抽出する共通 helper。

全関数 fail-open: ファイル不在・読取失敗・未知フォーマットは空文字を返す。
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REVIEW_REPLY_PATH = REPO_ROOT / "docs" / "handoff" / "review_reply.md"


def read_decision(path: Path) -> str:
    """review_reply.md の判定行から 'approve' / 'request_changes' を返す。

    判定対象: # 見出し行を除く行のうち、stripped が 'approve' または
    'request changes' / 'request_changes' で始まる最初の行。
    判定不能・ファイル不在は '' を返す（fail-open）。
    """
    if not path.exists():
        return ""
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return ""
    for line in text.splitlines():
        stripped = line.strip().lower()
        if stripped.startswith("#"):
            continue
        if stripped.startswith("request changes") or stripped.startswith("request_changes"):
            return "request_changes"
        if stripped.startswith("approve"):
            return "approve"
    return ""


def read_concerns(path: Path) -> str:
    """review_reply.md の ## 懸念 セクション本文を返す。取得不能は ''（fail-open）。"""
    if not path.exists():
        return ""
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return ""
    m = re.search(r'^##\s+懸念[^\n]*\n(.*?)(?=^##|\Z)', text, re.MULTILINE | re.DOTALL)
    return m.group(1).strip() if m else ""
