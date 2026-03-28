# 設計書インデックス

このファイルは設計書の一覧・責務・更新トリガー条件を管理する。
ローカル `docs/` が当面の正本。将来 Google ドキュメントへ移行予定。

## 優先度: 今すぐ必要

| doc_id | ファイル (ローカル) | 概要 | 更新トリガー |
|---|---|---|---|
| `system_overview` | `docs/system_overview.md` | システム全体の目的・構成概要 | 主要コンポーネント追加・削除時 |
| `architecture` | `docs/system_architecture.md` | FastAPI/React/DB/外部API の依存関係図 | 依存サービス追加・削除時 |
| `process_flow` | `docs/sequence_flow.md` | バッチ処理5ステップのシーケンス | `batch_runner.py`, `*_client.py` 変更時 |
| `api_design` | `docs/api_design.md` | REST API エンドポイント仕様 | `app/api/*.py`, `app/schemas.py` 変更時 |
| `non_functional` | `docs/non_functional_requirements.md` | タイムアウト・secrets制約・レート制限 | `CLAUDE.md` の制約変更時 |
| `runbook` | `docs/runbook.md` | バッチ起動・キャッシュ削除・障害対応手順 | 運用手順変更時 |
| `adr` | `docs/adr.md` | Architecture Decision Records | 設計判断が発生した時 |

## 優先度: 後回し

| doc_id | ファイル (ローカル) | 概要 | 作成タイミング |
|---|---|---|---|
| `data_model` | `docs/data_model.md` | DB テーブル・カラム設計（ER図） | DB変更が本格化した時 |
| `ui_design` | `docs/ui_design.md` | 画面遷移・レイアウト | フロントエンドが固まった時 |
| `functional_requirements` | `docs/functional_requirements.md` | 機能一覧の詳細 | MVP機能確定後 |

## 設計書の現在の状態

| doc_id | 状態 |
|---|---|
| `system_overview` | 作成済み (`docs/system_overview.md`) |
| `architecture` | 作成済み (`docs/system_architecture.md`) |
| `process_flow` | 作成済み (`docs/sequence_flow.md`) |
| `api_design` | 作成済み (`docs/api_design.md`) |
| `non_functional` | 作成済み (`docs/non_functional_requirements.md`) |
| `runbook` | 作成済み (`docs/runbook.md`) |
| `adr` | 作成済み (`docs/adr.md`) |
| `orchestrator_design` | 作成済み (`docs/orchestrator_design.md`) |

## 更新フロー

1. `generate_design_update_packet.py` を実行
2. `docs/design_update_packet.md` を確認
3. 該当設計書を更新（または後回しと判断）
4. commit/push
