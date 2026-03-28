# tools/ai_orchestrator/redaction.py
"""
OpenAI API に渡す前に secrets をマスクする。

>>> redact("password=hunter2 and code=normal")
'password=[REDACTED] and code=normal'
"""
from __future__ import annotations

import re

# (パターン, 置換文字列) のリスト。順番に適用する。
# 注意: 誤検知を防ぐため、高精度なパターンのみを対象とする。
_RULES: list[tuple[re.Pattern[str], str]] = [
    # OpenAI / Anthropic スタイルの API キー
    (re.compile(r"sk-[A-Za-z0-9_\-]{20,}"), "[REDACTED]"),
    # PostgreSQL / MySQL / SQLite 接続文字列
    (re.compile(r"(postgresql|mysql|sqlite)://[^\s\"']+"), r"\1://[REDACTED]"),
    # key=value / key: value 形式の secrets（行末 or 空白まで）
    (
        re.compile(
            r"(?i)(password|secret|api[_\-]?key|access[_\-]?token|refresh[_\-]?token"
            r"|client[_\-]?secret|auth[_\-]?token)\s*[=:]\s*(\S+)"
        ),
        r"\1=[REDACTED]",
    ),
    # AWS スタイルのアクセスキー（AKIA で始まる 20 文字英数字）
    (re.compile(r"AKIA[A-Z0-9]{16}"), "[REDACTED]"),
]


def redact(text: str) -> str:
    """テキスト中の secrets パターンを [REDACTED] に置き換えて返す。"""
    for pattern, replacement in _RULES:
        text = pattern.sub(replacement, text)
    return text


def redact_dict_fields(data: dict, fields: list[str]) -> dict:
    """
    dict の指定フィールドに redact() を適用したコピーを返す。
    フィールドが存在しない・None の場合はスキップ。
    """
    result = dict(data)
    for field in fields:
        if result.get(field):
            result[field] = redact(str(result[field]))
    return result
