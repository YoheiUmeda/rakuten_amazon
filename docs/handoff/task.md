---
task_id: "0001"
title: "README ローカル起動手順に Windows 補足を追加"
slug: "readme-windows-setup-note"
status: approved
# status の定義:
#   draft   : ローカルのみ。secrets_checked: false のまま push 禁止。
#   pending : secrets確認済み・GitHub掲載済み・ChatGPTレビュー待ち。
#   approved: Claude Code 実行可。main ブランチに承認済み push 済み。
#   done    : 完了。docs/handoff/archive/ へ移動する。
approved_at: "2026-03-29T00:00:00+09:00"
version: 1
updated: 2026-03-29
secrets_checked: true
# secrets_checked: false のまま push しないこと。
# push 前に以下を確認し true に変更する:
#   - .env の内容が含まれていないか
#   - RAKUTEN_APP_ID / KEEPA_API_KEY / DATABASE_URL 等が含まれていないか
#   - SP-API の refresh_token / client_secret が含まれていないか
---

<!-- 正本: main ブランチの docs/handoff/task.md -->
<!-- GitHub URL: https://github.com/YoheiUmeda/rakuten_amazon/blob/main/docs/handoff/task.md -->

## タスク
README.md のバックエンド起動手順（`source venv/bin/activate`）の下に、
Windows PowerShell 環境向けの補足コマンド `.\venv\Scripts\Activate.ps1` を1行追加する。

## 背景と目的
handoff MVP の運用テストを兼ねた最小変更。
Linux/Mac 向けの `source` コマンドのみ記載されており、
Windows PowerShell では `.\venv\Scripts\Activate.ps1` が正しいため補足する。

## 実施条件・制約
- README.md の該当箇所のみ変更する
- コードロジック・設定ファイルには触れない
- 変更は1〜2行以内にする

## raw evidence
（変更前後の diff は作業後に確認）

## 除外確認
- .env / APIキー / トークン: 未含有（確認済み）
