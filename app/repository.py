# app/repository.py
from sqlalchemy.orm import Session
from .db import SessionLocal                # ★ db.py に合わせる
from .models import PriceSnapshot
from .schemas import PriceResult


def save_price_results(results: list[PriceResult]) -> None:
    if not results:
        return

    with SessionLocal() as db:
        objects: list[PriceSnapshot] = []

        for r in results:
            # ★ ここで必ずAmazon URLを組み立てる
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
                diff=r.diff,
                pass_filter=r.pass_filter,
                checked_at=r.checked_at,
            )
            objects.append(obj)

        db.add_all(objects)
        db.commit()
