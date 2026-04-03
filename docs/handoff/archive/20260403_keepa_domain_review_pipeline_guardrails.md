# 棚卸し: Keepa domain 修正 / レビューパイプライン改善とガードレール追加

日付: 2026-04-03
コミット: 1b13c8e, 4915381, bceeed9

---

## 非エンジニア向け要約

- Amazon 日本向け商品の価格がほぼ取れていなかった問題を修正（カナダ向け設定になっていた）
- AI レビューに変更の文脈（目的・既知の非ブロッカー）を正しく渡せるよう改善した
- 設定ファイルを手動で書き換えた後にコマンドが無言上書きしてしまう事故を防ぐ安全策を追加

## エンジニア向け要約

| コミット | 内容 |
|---|---|
| `1b13c8e` | `get_keepa_prices.py`: `KEEPA_DOMAIN` デフォルトを `6`(Canada) → `5`(Japan) に修正 |
| `4915381` | `orchestrator.py`: `review_mode` / `expected_non_blockers` を GPT プロンプトに出力するよう追加 |
| `bceeed9` | `run_review.py`: `--save-only` 時に既存 review_request.json があれば exit 1（`--overwrite` 明示必要） |

## 変更理由

- **KEEPA_DOMAIN**: `keepa_client.py` の finder は既に `domain=5` を使っていたが、`get_keepa_prices.py` の product API だけ `domain=6` のままだった。日本向け ASIN 8件テストで domain=5 は 8/8 取得、domain=6 は 2/8 のみと確認。
- **orchestrator**: `review_request.json` に `review_mode` / `expected_non_blockers` を書いても GPT プロンプトに渡されておらず、文脈なしのフル品質レビューが行われていた。
- **run_review --save-only**: 手動で `expected_non_blockers` 等を書いた `review_request.json` が `--save-only` 再実行で無言上書きされる事故が発生した。

## 挙動差分

### KEEPA_DOMAIN
- before: domain=6 (Canada) → 日本向け ASIN の価格がほぼ None
- after: domain=5 (Japan) → 価格取得率が大幅改善

### orchestrator
- before: `review_mode` / `expected_non_blockers` はプロンプトに含まれない
- after: `review_request.json` にこれらが含まれていれば orchestrator のプロンプトへ渡される

### run_review --save-only
- before: 既存 review_request.json を無言上書き
- after: 既存ファイルあり + `--overwrite` なし → exit 1 + エラーメッセージ

## 運用上の注意点

- `KEEPA_DOMAIN` を変更したい場合は `.env` に `KEEPA_DOMAIN=6` と明示する
- `--save-only` で既存ファイルを上書きしたい場合は `--overwrite` を追加する
- `expected_non_blockers` は `review_request.json` に含めれば orchestrator のプロンプトへ渡される。`cycle_to_review_request.py` が条件付きで自動生成するほか、手動追記も有効
