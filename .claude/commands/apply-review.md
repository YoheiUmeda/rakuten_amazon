# apply-review

`docs/handoff/review_reply.md` のレビュー結果を読み、result.md を更新する。

## Steps
1. `docs/handoff/review_reply.md` を確認する（## Decision が記入済みかチェック）
2. 内容に問題なければ Python スクリプトで処理する:
   ```
   # 確認のみ（変更なし・任意）
   venv/Scripts/python -m tools.ai_orchestrator.apply_review --dry-run

   # 通常実行（Approve 時は --auto-approve を推奨）
   venv/Scripts/python -m tools.ai_orchestrator.apply_review --auto-approve

   # task.md の done化と archive移動まで自動化する場合（--auto-approve 成功時のみ有効）
   venv/Scripts/python -m tools.ai_orchestrator.apply_review --auto-approve --auto-archive
   ```
3. **Approve の場合:**
   - result.md の `status: review-pending` → `status: reviewed` に自動更新済み
   - `--auto-approve` を付けた場合、`cycle_manager approve` も自動実行されるため手動不要
   - `--auto-archive` を追加した場合、task.md の status を `done` にして `archive/` へ移動も自動実行
   - `--auto-archive` は `--auto-approve` 成功時のみ有効（cycle 未確定時は task.md を移動しない）
4. **Request changes の場合:**
   - スクリプトが Issues / Required changes を出力する
   - 変更を実施後、fill_result → レビュー依頼を再実施する
