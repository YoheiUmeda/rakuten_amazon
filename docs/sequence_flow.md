# 処理フロー / シーケンス図

## バッチ処理 全体フロー

```
[Human / Scheduler]
        ↓ run_batch_once(query)
[1] get_asins_from_finder(query)
        → Keepa Product Finder API
        ← ASIN リスト (N 件)

[2] get_amazon_prices(asins)
        → Amazon SP-API (GetItemOffers)
        ← {asin: {price, ...}} (priced 件)

[2.5] get_amazon_fees_estimate(offer_data)
        → Amazon SP-API (EstimateMyFeesEstimate)
        ← {asin: {total_fee, ...}}

[3] prefilter_for_rakuten(data, min_profit, min_price)
        → (filtered, excluded)  ← reject_reason 付き

[3.5] get_rakuten_info(filtered)
        → 楽天 Ichiba API (商品検索)
        ← {asin: {rakuten_price, rakuten_url, ...}}

[4] calculate_price_difference(data)
        → {asin: {profit_total, roi_percent, ...}}

[5] export_asin_dict_to_excel(result)  + save_price_results(price_results)
        → Excel ファイル + PostgreSQL
```

## reject_reason 一覧

| reason | 段階 | 意味 |
|---|---|---|
| `price_too_low(N)` | prefilter | 販売価格 < min_price |
| `fee_none` | prefilter | 手数料が取得できない |
| `low_max_profit(N)` | prefilter | 最大利益 < 閾値 |
| `cached_no_hit` | rakuten_client | キャッシュに空配列が保存済み |
| `no_rakuten_hit` | rakuten_client | 全検索でヒット0件 |
| `all_rakuten_items_rejected` | rakuten_client | ヒットしたが全件フィルタで除外 |
