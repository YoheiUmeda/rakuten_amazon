# API設計 / インターフェース設計

## ベース URL
`http://localhost:8000`

## エンドポイント一覧

### GET /prices/summary
最新スナップショットの集計サマリを返す。

**レスポンス例:**
```json
{
  "latest_checked_at": "2026-03-28T10:00:00",
  "count": 42,
  "avg_profit": 1234.5,
  "avg_roi": 18.3
}
```

### POST /prices
価格一覧を検索する。

**リクエスト (PriceSearchCondition):**

| フィールド | 型 | デフォルト | 説明 |
|---|---|---|---|
| `keyword` | str | null | タイトル・ASIN 部分一致 |
| `min_profit` | float | null | 利益下限 (円) |
| `min_roi` | float | null | ROI 下限 (%) |
| `only_pass_filter` | bool | false | pass_filter=true のみ |
| `pass_min_profit` | float | null | pass 判定利益閾値 |
| `pass_min_roi` | float | null | pass 判定 ROI 閾値 |
| `limit` | int | 1000 | 最大件数 |

**レスポンス (PriceResponse):**
```json
{
  "items": [...],
  "total": 42
}
```

## バッチ API（内部）

### POST /batch/run
バッチを手動トリガーする（FastAPI 経由）。
