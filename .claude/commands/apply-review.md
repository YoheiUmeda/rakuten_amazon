# apply-review

`docs/handoff/review_reply.md` のレビュー結果を読み、result.md を更新する。

## Steps
1. `docs/handoff/review_reply.md` を確認する（## Decision が記入済みかチェック）
2. 内容に問題なければ Python スクリプトで処理する:
   ```
   # 確認のみ（変更なし）
   venv/Scripts/python -m tools.ai_orchestrator.apply_review --dry-run

   # 実行
   venv/Scripts/python -m tools.ai_orchestrator.apply_review
   ```
3. **Approve の場合:**
   - result.md の `status: review-pending` → `status: reviewed` に自動更新済み
   - （手動）task.md の status を `done` にして `docs/handoff/archive/` へ移動する
4. **Request changes の場合:**
   - スクリプトが Issues / Required changes を出力する
   - 変更を実施後、fill_result → レビュー依頼を再実施する
