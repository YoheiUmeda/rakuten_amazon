# prefilter.py

from __future__ import annotations

from typing import Any, Dict, Tuple


def prefilter_for_rakuten(
    asin_map: Dict[str, Dict[str, Any]],
    min_max_possible_profit: int = 1500,
    min_price: int = 3000,
    min_sales_rank_drops30: int = 0,
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, str]]:
    """
    楽天APIを叩く前に、
    「楽天仕入れで利益が出る見込みがあるASINだけ」を残すための粗フィルタ。

    ロジック:
      - sale_price: Amazon販売価格（優先順: price → amazon_price → current_NEW/current_new）
      - total_fee : FBA/紹介料など、総手数料（優先順: total_fee → fee）
      - max_possible_profit = sale_price - total_fee
        → 仕入れ原価を 0 円と仮定したときの「上限利益」

    条件:
      - sale_price < min_price         → 除外
      - max_possible_profit < min_max_possible_profit → 除外
      - min_sales_rank_drops30 > 0 かつ sales_rank_drops30 < min_sales_rank_drops30 → 除外
        （sales_rank_drops30 が None/欠損の場合は fail-open で通す）
    """

    filtered: Dict[str, Dict[str, Any]] = {}
    excluded: Dict[str, str] = {}

    for asin, info in asin_map.items():
        if info is None:
            excluded[asin] = "info_none"
            continue

        # --- 販売価格の取得（プロジェクトの実データに合わせて優先度を定義） ---
        raw_sale_price = (
            info.get("price")
            or info.get("amazon_price")
            or info.get("current_NEW")
            or info.get("current_new")
        )
        if raw_sale_price is None:
            excluded[asin] = "price_none"
            continue

        try:
            sale_price = float(raw_sale_price)
        except (TypeError, ValueError):
            excluded[asin] = "price_invalid"
            continue

        # 安すぎる商品はそもそも対象外
        if sale_price < min_price:
            excluded[asin] = f"price_too_low({sale_price:.0f})"
            continue

        # --- 手数料の取得 ---
        raw_total_fee = info.get("total_fee") or info.get("fee")
        if raw_total_fee is None:
            excluded[asin] = "fee_none"
            continue

        try:
            total_fee = float(raw_total_fee)
        except (TypeError, ValueError):
            excluded[asin] = "fee_invalid"
            continue

        # 仕入れ原価が 0 円でも、これ以下の利益しか出ないなら切る
        max_possible_profit = sale_price - total_fee
        if max_possible_profit < min_max_possible_profit:
            excluded[asin] = f"low_max_profit({max_possible_profit:.0f})"
            continue

        # 販売速度フィルタ（min_sales_rank_drops30 > 0 のときのみ有効）
        if min_sales_rank_drops30 > 0:
            drops = info.get("sales_rank_drops30")
            if drops is not None and drops < min_sales_rank_drops30:
                excluded[asin] = f"low_sales_velocity({drops})"
                continue

        filtered[asin] = info

    return filtered, excluded
