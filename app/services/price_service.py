# app/services/price_service.py
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models import PriceSnapshot
from app.schemas import PriceSearchCondition, PriceItem


def search_prices(db: Session, condition: PriceSearchCondition) -> List[PriceItem]:
    latest_checked_at_subq = db.query(
        func.max(PriceSnapshot.checked_at)
    ).scalar_subquery()

    q = db.query(PriceSnapshot).filter(
        PriceSnapshot.checked_at == latest_checked_at_subq
    )

    q = q.filter(PriceSnapshot.pass_filter == True)

    if condition.keyword:
        like = f"%{condition.keyword}%"
        q = q.filter(PriceSnapshot.title.ilike(like))

    if condition.min_profit is not None:
        q = q.filter(PriceSnapshot.profit_per_item >= condition.min_profit)

    if condition.min_roi is not None:
        q = q.filter(PriceSnapshot.roi_percent >= condition.min_roi)

    q = q.order_by(PriceSnapshot.profit_per_item.desc())

    if condition.limit:
        q = q.limit(condition.limit)

    rows = q.all()

    items: List[PriceItem] = [
        PriceItem(
            asin=row.asin,
            title=row.title,
            amazon_price=row.amazon_price,
            rakuten_price=row.rakuten_price,
            profit_per_item=row.profit_per_item,
            roi_percent=row.roi_percent,
            checked_at=row.checked_at,
            amazon_url=row.amazon_url,
            rakuten_url=row.rakuten_url,
        )
        for row in rows
    ]

    return items
