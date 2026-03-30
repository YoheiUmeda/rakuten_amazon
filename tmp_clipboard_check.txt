<!-- review_request
     generated_at: 2026-03-30T23:02:02+09:00
     task_id: (none)
     template_version: 1
     commit: a207cb0 -->

以下の実行結果レポートをレビューし、人間が確認・承認できる形で整理してください。

**確認ポイント:**
- 結論は明確か（何をした・成功/失敗が分かるか）
- 目的と結果が一致しているか
- diff と変更ファイルは一致しているか
- 影響範囲は妥当か（想定外の副作用がないか）
- テスト結果は十分か（pass/fail が明示されているか）
- secrets が含まれていないか（.env / APIキー / トークン / DB接続文字列）
- 未確定点・懸念は適切に記録されているか
- 重点レビュー観点に回答できるか

**回答形式:**

## 実行結果の要点
（何をした・どのファイルが変わった・テストの状況を箇条書きで）

## diff / テスト結果の確認
（diff と変更ファイルの整合性、テスト pass/fail、secrets 混入チェック）

## 懸念点（あれば）
（品質・副作用・未確定点・影響範囲の観点から）

## Approve / Request changes
（archive 可 → Approve / 追加対応必要 → Request changes、理由1行）

https://github.com/YoheiUmeda/rakuten_amazon/blob/main/docs/handoff/result.md