# app/api/prices.py
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import PriceSnapshot
from app.schemas import PriceItem, PriceSearchCondition, PriceResponse

router = APIRouter()


@router.post("/prices", response_model=PriceResponse)
def search_prices(
    cond: PriceSearchCondition,
    db: Session = Depends(get_db),
) -> PriceResponse:
    q = db.query(PriceSnapshot)

    if cond.keyword:
        like = f"%{cond.keyword}%"
        q = q.filter(
            (PriceSnapshot.title.ilike(like)) |
            (PriceSnapshot.asin.ilike(like))
        )

    if cond.min_profit is not None:
        q = q.filter(PriceSnapshot.profit_per_item >= cond.min_profit)

    if cond.min_roi is not None:
        q = q.filter(PriceSnapshot.roi_percent >= cond.min_roi)

    # pass_filter では絞らない
    # q = q.filter(PriceSnapshot.pass_filter.is_(True))

    q = q.order_by(PriceSnapshot.checked_at.desc())

    if cond.limit:
        q = q.limit(cond.limit)

    rows: List[PriceSnapshot] = q.all()

    items: List[PriceItem] = [
        PriceItem(
            asin=r.asin,
            title=r.title or "",
            amazon_price=r.amazon_price,
            rakuten_price=r.rakuten_price,
            profit_per_item=r.profit_per_item,
            roi_percent=r.roi_percent,
            amazon_url=r.amazon_url,
            rakuten_url=r.rakuten_url,
        )
        for r in rows
    ]

    return PriceResponse(items=items, total=len(items))
