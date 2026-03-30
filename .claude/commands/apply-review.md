# apply-review

`docs/handoff/review_reply.md` のレビュー結果を読み、後続アクションを実行する。

## Steps
1. `docs/handoff/review_reply.md` を読む
2. `## Decision` セクションの判定を確認する（Approve / Request changes）
3. **Approve の場合:**
   - `docs/handoff/result.md` の `status: review-pending` → `status: reviewed` に変更
   - `docs/handoff/task.md` の status を `done` に変更することを提案する
4. **Request changes の場合:**
   - 必要な変更点を箇条書きで列挙する
   - result.md の status は変更しない
5. 3行で報告:
   Decision: Approve / Request changes
   Updated: <変更したファイル、なければ none>
   Next: <次のアクション>
