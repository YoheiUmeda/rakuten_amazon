# ChatGPT Handoff プロンプトテンプレート

## 正本の場所
- GitHub（primary）: `https://github.com/<owner>/<repo>/blob/main/docs/handoff/task.md`
- コピペ（fallback）: task.md の全文を末尾に貼る

## 使い方
1. task.md の status が `pending` になっていることを確認する
2. GitHub URL を ChatGPT に渡す（browsing 対応の場合）
   または task.md の全文をこのプロンプトの末尾に貼り付けて送信する
3. ChatGPT の出力を確認し、問題なければ task.md の status を `approved` に変更して push する

---

## ChatGPT への指示文（ここから下をそのまま使う）

以下の指示文をレビューし、人間が承認できる形で整理してください。

**確認ポイント:**
- タスクの内容は明確か
- secrets が含まれていないか（.env / APIキー / トークン / DB接続文字列）
- 実施条件・制約は適切か
- raw evidence は十分か（diff / test_output がある場合）
- 承認前に人間が判断すべき懸念点はあるか

**回答形式:**

## 指示内容の要点
（タスクの目的・変更内容・制約を箇条書きで）

## raw evidence の確認
（diff / test_output / reject_log が含まれているか、secrets が混入していないか）

## 懸念点（あれば）
（精度・安全性・副作用の観点から）

## 承認可否の判断材料
（このまま Claude Code に渡してよいか）

---

[ここに task.md の内容を貼る（GitHub URL を渡す場合は不要）]
