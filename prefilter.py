# prefilter.py

from __future__ import annotations

from typing import Any, Dict


def prefilter_for_rakuten(
    asin_map: Dict[str, Dict[str, Any]],
    min_max_possible_profit: int = 1500,
    min_price: int = 3000,
) -> Dict[str, Dict[str, Any]]:
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
    """

    filtered: Dict[str, Dict[str, Any]] = {}

    for asin, info in asin_map.items():
        if info is None:
            continue

        # --- 販売価格の取得（プロジェクトの実データに合わせて優先度を定義） ---
        raw_sale_price = (
            info.get("price")
            or info.get("amazon_price")
            or info.get("current_NEW")
            or info.get("current_new")
        )
        if raw_sale_price is None:
            continue

        try:
            sale_price = float(raw_sale_price)
        except (TypeError, ValueError):
            continue

        # 安すぎる商品はそもそも対象外
        if sale_price < min_price:
            continue

        # --- 手数料の取得 ---
        raw_total_fee = info.get("total_fee") or info.get("fee")
        if raw_total_fee is None:
            continue

        try:
            total_fee = float(raw_total_fee)
        except (TypeError, ValueError):
            continue

        # 仕入れ原価が 0 円でも、これ以下の利益しか出ないなら切る
        max_possible_profit = sale_price - total_fee
        if max_possible_profit < min_max_possible_profit:
            continue

        filtered[asin] = info

    return filtered
