# prefilter.py

from typing import Dict, Any


def prefilter_for_rakuten(
    asin_map: Dict[str, Dict[str, Any]],
    min_max_possible_profit: int = 1500,
    min_price: int = 3000,
) -> Dict[str, Dict[str, Any]]:
    """
    楽天APIを叩く前に、そもそも「楽天仕入れで利益が出る見込みがあるか」を
    雑にチェックして、価値のあるASINだけ残す。

    - max_possible_profit = Amazon販売価格 - total_fee（仕入れ0円と仮定した「上限利益」）
    - それが min_max_possible_profit 未満なら切る
    - Amazon価格が安すぎるもの（min_price未満）も切る

    ※ amazon_price / total_fee のキー名はプロジェクトに合わせて直すこと。
    """

    filtered: Dict[str, Dict[str, Any]] = {}

    for asin, info in asin_map.items():
        if info is None:
            continue

        # ここはあなたの実際のキー名に合わせて修正して
        sale_price = (
            info.get("amazon_price")  # 例: amazon_price というキーにしている場合
            or info.get("current_new")  # 例: current_NEW を持たせている場合
            or info.get("price")  # 例: 汎用 price で持っている場合
        )
        total_fee = info.get("total_fee")  # amazon_fee.annotate で入れてるやつ

        if sale_price is None or total_fee is None:
            continue

        # 安すぎる商品はそもそも対象外
        if sale_price < min_price:
            continue

        # 仕入れ原価が0円だとしても、これ以下の利益しか出ないなら切る
        max_possible_profit = sale_price - total_fee

        if max_possible_profit < min_max_possible_profit:
            continue

        filtered[asin] = info

    return filtered
