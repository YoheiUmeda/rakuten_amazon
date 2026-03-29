---
task_id: ""
title: ""
slug: ""
status: draft
# status の定義:
#   draft   : ローカルのみ。secrets_checked: false のまま push 禁止。
#   pending : secrets確認済み・GitHub掲載済み・ChatGPTレビュー待ち。
#   approved: Claude Code 実行可。main ブランチに承認済み push 済み。
#   done    : 完了。docs/handoff/archive/ へ移動する。
approved_at: null
version: 1
updated: YYYY-MM-DD
secrets_checked: false
# secrets_checked: false のまま push しないこと。
# push 前に以下を確認し true に変更する:
#   - .env の内容が含まれていないか
#   - RAKUTEN_APP_ID / KEEPA_API_KEY / DATABASE_URL 等が含まれていないか
#   - SP-API の refresh_token / client_secret が含まれていないか
---

<!-- 正本: main ブランチの docs/handoff/task.md -->
<!-- GitHub URL: https://github.com/<owner>/<repo>/blob/main/docs/handoff/task.md -->

## タスク


## 背景と目的


## 実施条件・制約
-

## raw evidence
<!-- diff / test_output / reject_log のみ。secrets を含めないこと。 -->


## 除外確認
- .env / APIキー / トークン: 未含有（確認済み）
