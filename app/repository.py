# app/repository.py
from __future__ import annotations

from typing import List

from .db import get_session
from .models import PriceSnapshot
from .schemas import PriceResult


def save_price_results(results: List[PriceResult]) -> None:
    """
    バッチやGUIから渡された PriceResult をまとめて PriceSnapshot に保存する。
    """
    if not results:
        return

    with get_session() as db:
        objects: List[PriceSnapshot] = []

        for r in results:
            # Amazon URL は必ず補完しておく
            amazon_url = r.amazon_url or f"https://www.amazon.co.jp/dp/{r.asin}"

            obj = PriceSnapshot(
                asin=r.asin,
                title=r.title or "",
                amazon_url=amazon_url,
                rakuten_url=r.rakuten_url,
                amazon_price=r.amazon_price,
                rakuten_price=r.rakuten_price,
                profit_per_item=r.profit_per_item,
                roi_percent=r.roi_percent,
                pass_filter=r.pass_filter,
                checked_at=r.checked_at,
            )
            objects.append(obj)

        db.add_all(objects)
        db.commit()
