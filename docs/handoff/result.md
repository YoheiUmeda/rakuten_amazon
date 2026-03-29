---
task_id: ""
status: review-pending
# status の定義:
#   review-pending : ChatGPT レビュー待ち（push 済み）
#   reviewed       : 人間確認済み。task.md を done にして archive 可。
generated_at: YYYY-MM-DDTHH:MM:SS+09:00
secrets_checked: false
# secrets_checked: false のまま push しないこと。
# push 前に以下を確認し true に変更する:
#   - diff に .env の内容が含まれていないか
#   - APIキー / トークン / DB接続文字列が含まれていないか
---

<!-- 正本: main ブランチの docs/handoff/result.md -->
<!-- GitHub URL: https://github.com/YoheiUmeda/rakuten_amazon/blob/main/docs/handoff/result.md -->

## 結論
<!-- 何をしたか・成功/失敗・1〜3行で -->

## 目的
<!-- task.md の「タスク」から1〜2行でコピー -->

## 変更ファイル
-

## 影響範囲
<!-- 変更の影響が及ぶ範囲（他モジュール・API・DB等）。なければ「なし」 -->

## diff
<!-- git diff の全文または主要部分。secrets を含めないこと。 -->
```diff

```

## テスト結果
<!-- pytest 出力または test summary。省略する場合はその理由を書く。 -->
```

```

## ログ要約
<!-- 警告・エラー・重要なログ行。不要なら「なし」と書く。 -->

## 未確定点・懸念
<!-- Claude が判断できなかった点、次に確認してほしいこと。なければ「なし」 -->

## 重点レビュー観点
<!-- ChatGPT に特に見てほしい点。なければ「なし」 -->

## secrets 確認
- .env / APIキー / トークン: 未含有（確認済み）
