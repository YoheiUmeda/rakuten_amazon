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
- diff と変更ファイルは一致しているか
- テスト結果は十分か（pass/fail が明示されているか）
- secrets が含まれていないか（.env / APIキー / トークン / DB接続文字列）
- 未確定点・懸念は適切に記録されているか
- 次のアクション（archive・追加対応）を判断するのに十分な情報があるか

**回答形式:**

## 実行結果の要点
（何をした・どのファイルが変わった・テストの状況を箇条書きで）

## diff / テスト結果の確認
（diff と変更ファイルの整合性、テスト pass/fail、secrets 混入チェック）

## 懸念点（あれば）
（品質・副作用・未確定点の観点から）

## 承認可否の判断材料
（task.md を done にして archive してよいか）

---

[ここに result.md の内容を貼る（GitHub URL を渡す場合は不要）]
