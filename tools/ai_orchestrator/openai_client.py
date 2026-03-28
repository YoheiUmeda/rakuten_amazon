# tools/ai_orchestrator/openai_client.py
"""
OpenAI Responses API の薄いラッパー。
openai パッケージは lazy import（--dry-run 時はインポートしない）。
"""
from __future__ import annotations

import os


def call_review(
    system_prompt: str,
    user_content: str,
    model: str | None = None,
    api_key: str | None = None,
) -> str:
    """
    OpenAI Responses API を呼び出し、レビュー結果テキストを返す。

    Args:
        system_prompt: .ai/prompts/review_system.md の内容
        user_content:  レビュー依頼の本文（redact 済み）
        model:         使用モデル（None なら OPENAI_MODEL env var → gpt-4o）
        api_key:       API キー（None なら OPENAI_API_KEY env var）

    Raises:
        ImportError: openai パッケージが未インストールの場合
        ValueError:  api_key が未設定の場合
    """
    try:
        import openai  # lazy import
    except ImportError as e:
        raise ImportError(
            "openai パッケージがインストールされていません。\n"
            "実行: venv/Scripts/pip install \"openai>=1.0.0\""
        ) from e

    resolved_key = api_key or os.getenv("OPENAI_API_KEY")
    if not resolved_key:
        raise ValueError(
            "OPENAI_API_KEY が未設定です。.env に OPENAI_API_KEY=sk-... を追加してください。"
        )

    resolved_model = model or os.getenv("OPENAI_MODEL", "gpt-4o")

    client = openai.OpenAI(api_key=resolved_key)

    response = client.responses.create(
        model=resolved_model,
        instructions=system_prompt,
        input=user_content,
    )

    return response.output_text
