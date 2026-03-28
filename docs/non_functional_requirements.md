# 非機能要件

## タイムアウト
- すべての `requests.get` 呼び出しに `timeout=(10, 30)` を必須とする
- 接続タイムアウト: 10 秒 / 読み取りタイムアウト: 30 秒

## レート制限・スリープ
- 楽天 API: `RAKUTEN_SLEEP_TIME`（float）ごとにスリープ。`float()` で読む（`int()` 禁止）
- Keepa API: レート制限は Keepa SDK に委譲

## Secrets 管理
- `.env` ファイルは Git にコミットしない
- OpenAI / ChatGPT API に渡す際、以下を除外する:
  - `RAKUTEN_APP_ID`, `KEEPA_API_KEY`, `DATABASE_URL`
  - SP-API: `refresh_token`, `client_secret`
  - AWS: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`

## 利益・手数料計算の安全ルール
- `fee=None` は絶対に 0 として扱わない
- `pass_filter` は安全側（厳しめ）に倒す
- `pass_filter / fee / profit` ロジックの変更は承認必須

## エラー処理
- 楽天 API: `search_rakuten_product_api` / `search_ichiba_from_product` は retry なし。429 は `except Exception` で吸収
- DB 保存失敗: `RuntimeError`（DATABASE_URL 未設定）はスキップ扱い
