# ChatGPT Result Review プロンプトテンプレート

## 正本の場所
- GitHub（primary）: `https://github.com/<owner>/<repo>/blob/main/docs/handoff/result.md`
- コピペ（fallback）: result.md の全文を末尾に貼る

## 使い方

### CLI（推奨）
```bash
venv/Scripts/python -m tools.ai_orchestrator.fill_result --print-chat-prompt
```
出力をそのままコピーして ChatGPT に貼る。

### 手動（fallback）
1. result.md の status が `review-pending` になっていることを確認する
2. 下記「ChatGPT への指示文」をコピーし、末尾に GitHub URL または result.md 全文を追記して送信する
3. ChatGPT の出力を確認し、問題なければ result.md の status を `reviewed` に変更する
4. task.md の status を `done` にして archive へ移動する

---

## ChatGPT への指示文（ここから下をそのまま使う）

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

**回答形式（固定）:**

## Decision
Approve または Request changes のどちらか1行で明示する。

## Issues
問題点を箇条書き（なければ「なし」）。
secrets / テスト失敗 / diff不整合 / 副作用を含む。

## Required changes
対応必須の変更点を箇条書き（Approve の場合は「なし」）。

## Notes
任意コメント（懸念・提案・軽微な指摘）。不要なら省略可。

---

[ここに result.md の内容を貼る（GitHub URL を渡す場合は不要）]
