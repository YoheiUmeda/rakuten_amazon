---
task_id: "20260404-triage"
title: "候補商品 triage 分類列追加（deal_status / block_reason / next_action）"
slug: "triage-classification"
status: done
# status の定義:
#   draft   : ローカルのみ。secrets_checked: false のまま push 禁止。
#   pending : secrets確認済み・GitHub掲載済み・ChatGPTレビュー待ち。
#   approved: Claude Code 実行可。main ブランチに承認済み push 済み。
#   done    : 完了。docs/handoff/archive/ へ移動する。
approved_at: null
version: 1
updated: "2026-04-04"
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
候補商品の triage 設計と最小実装。deal_status / block_reason / next_action の分類列を追加する。

## 背景と目的
pass_filter の二値判定だけでは「仕入候補」「スキップ」「要確認」の区別ができなかった。
自動判定できる範囲でステータスを付与し、Excel出力の先頭列で視認できるようにする。

## 実施条件・制約
- out-of-cycle 実績記録（cycle_manager 管理外で実施・push）
- 対象コミット: 3a90380
- unlock_candidate / reject_cart_price / reject_variation_mismatch は今回 scope 外

## raw evidence
<!-- diff / test_output / reject_log のみ。secrets を含めないこと。 -->


## 除外確認
- .env / APIキー / トークン: 未含有（確認済み）
