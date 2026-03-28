# tools/ai_orchestrator/design_doc_mapper.py
"""
変更ファイルのリストを受け取り、更新が必要な設計書IDを返す。

usage:
    from tools.ai_orchestrator.design_doc_mapper import map_changed_files
    result = map_changed_files(["app/api/prices.py", "batch_runner.py"])
    # => {"api_design": ["app/api/prices.py"], "process_flow": ["batch_runner.py"]}
"""
from __future__ import annotations

import fnmatch
from typing import Dict, List

# ソースファイルパターン → 設計書 ID のマッピング
# キー: glob パターン（fnmatch 形式）
# 値: 更新が必要な設計書 ID リスト
TRIGGER_MAP: Dict[str, List[str]] = {
    # バッチ処理コア
    "batch_runner.py":              ["process_flow", "system_overview"],
    "rakuten_client.py":            ["process_flow"],
    "amazon_fee.py":                ["process_flow"],
    "amazon_price.py":              ["process_flow"],
    "price_calculation.py":         ["process_flow"],
    "keepa_client.py":              ["process_flow", "architecture"],
    "prefilter.py":                 ["process_flow"],
    "spapi_client.py":              ["process_flow", "architecture"],
    # API層
    "app/api/*.py":                 ["api_design"],
    "app/schemas.py":               ["api_design", "data_model"],
    "app/models.py":                ["data_model", "api_design"],
    "app/repository.py":            ["data_model"],
    "app/db.py":                    ["data_model", "non_functional"],
    "app/main_fastapi.py":          ["architecture", "api_design"],
    # フロントエンド
    "frontend/src/*.tsx":           ["ui_design"],
    "frontend/src/*.ts":            ["ui_design"],
    "frontend/src/**/*.tsx":        ["ui_design"],
    "frontend/src/**/*.ts":         ["ui_design"],
    # 設定・環境
    ".env.example":                 ["non_functional"],
    "CLAUDE.md":                    ["non_functional"],
    "requirements*.txt":            ["architecture"],
    "docker-compose*.yml":          ["architecture", "runbook"],
    "Dockerfile*":                  ["architecture", "runbook"],
    # オーケストレーター自体
    "docs/orchestrator_design.md":  ["orchestrator_design"],
    "tools/ai_orchestrator/*.py":   ["orchestrator_design"],
}

# 設計書IDと人間が読めるラベルのマッピング
DOC_LABELS: Dict[str, str] = {
    "system_overview":          "システム概要",
    "architecture":             "システム構成図",
    "process_flow":             "処理フロー / シーケンス図",
    "api_design":               "API設計",
    "non_functional":           "非機能要件",
    "runbook":                  "運用設計 / Runbook",
    "adr":                      "変更履歴 / ADR",
    "data_model":               "データモデル / DB設計",
    "ui_design":                "UI設計 / 画面遷移図",
    "functional_requirements":  "機能一覧",
    "orchestrator_design":      "オーケストレーター設計",
}

# ローカルファイルパス（spec_index.md と同期）
DOC_PATHS: Dict[str, str] = {
    "system_overview":          "docs/system_overview.md",
    "architecture":             "docs/system_architecture.md",
    "process_flow":             "docs/sequence_flow.md",
    "api_design":               "docs/api_design.md",
    "non_functional":           "docs/non_functional_requirements.md",
    "runbook":                  "docs/runbook.md",
    "adr":                      "docs/adr.md",
    "data_model":               "docs/data_model.md",
    "ui_design":                "docs/ui_design.md",
    "functional_requirements":  "docs/functional_requirements.md",
    "orchestrator_design":      "docs/orchestrator_design.md",
}


def map_changed_files(changed_files: List[str]) -> Dict[str, List[str]]:
    """
    変更ファイルリストを受け取り、更新が必要な設計書ID → 触れたファイル一覧 を返す。

    Args:
        changed_files: git diff --name-only 相当のファイルパスリスト

    Returns:
        {doc_id: [matched_file, ...]}  — 空の場合は更新対象なし
    """
    result: Dict[str, List[str]] = {}

    for changed in changed_files:
        for pattern, doc_ids in TRIGGER_MAP.items():
            if fnmatch.fnmatch(changed, pattern):
                for doc_id in doc_ids:
                    result.setdefault(doc_id, [])
                    if changed not in result[doc_id]:
                        result[doc_id].append(changed)

    return result
