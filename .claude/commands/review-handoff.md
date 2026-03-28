# review-handoff

以下の手順で `review_request.json` の下書きを生成してください。
**orchestrator は自動実行しない。** 人間確認後に手動で実行する。

## 手順

### Step 1: 情報収集
以下をユーザーに確認する（回答がなければデフォルトを使う）:
- `task`: 今回のレビュー依頼の説明（必須）
- `files`: 対象ファイル（省略時は git diff HEAD から自動取得）
- `test-cmd`: テストコマンド（例: `venv/Scripts/python -m pytest tests/ -v`）
- `related-code`: 関連コードファイル（省略可、複数指定で内容を取り込む）
- `open-questions`: 未解決の疑問点（複数可）
- `constraints`: 守るべき制約（複数可、デフォルト: "pass_filter / fee / profit ロジックには触れない"）

### Step 2: dry-run プレビュー
収集した情報で下記コマンドを実行し、JSON 内容をユーザーに提示する:

```
venv/Scripts/python -m tools.ai_orchestrator.generate_review_request \
  --task "<task>" \
  [--files <file1> <file2> ...] \
  [--test-cmd "<cmd>"] \
  [--related-code <file1> <file2> ...] \
  [--open-questions "<q1>" "<q2>"] \
  [--constraints "<c1>" "<c2>"] \
  --dry-run
```

### Step 3: ユーザー確認
dry-run の出力を提示し、修正が必要か確認する。
- 問題なければ Step 4 へ
- 修正があれば引数を調整して Step 2 をやり直す

### Step 4: ファイル保存
ユーザーが OK を出したら `--output` を付けて再実行:

```
venv/Scripts/python -m tools.ai_orchestrator.generate_review_request \
  --task "<task>" \
  [--files <file1> <file2> ...] \
  [--test-cmd "<cmd>"] \
  [--run-tests] \
  [--related-code <file1> <file2> ...] \
  [--open-questions "<q1>" "<q2>"] \
  [--constraints "<c1>" "<c2>"] \
  --output .ai/handoff/review_request.json
```

### Step 5: 次のステップを案内（実行しない）
```
# レビューを実行するには（手動で実行してください）:
venv/Scripts/python -m tools.ai_orchestrator.orchestrator \
  --input .ai/handoff/review_request.json \
  --output docs/review_reply.md
```

## 注意事項
- `docs/review_reply.md` は `.gitignore` 済みのため commit されない
- `review_request.json` は機密情報を含む可能性があるため commit 前に要確認
- `pass_filter / fee / profit` ロジックへの言及は警告を出すこと
- `--related-code` で指定したファイルは内容が JSON に含まれる（最大 200行 / 4000文字）
