# app/api/prices.py
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_session
from app.schemas import PriceSearchCondition, PriceResponse
from app.repository import search_prices

# ここは「/prices」。main.py 側で prefix="/api" を付けているので
# 最終的なパスは /api/prices になる。
router = APIRouter(prefix="/prices", tags=["prices"])


@router.post("", response_model=PriceResponse)
def search_prices_endpoint(
    condition: PriceSearchCondition,
    db: Session = Depends(get_session),
) -> PriceResponse:
    """
    価格差リストを検索するAPI。

    - keyword: ASIN またはタイトル部分一致
    - min_profit: 最低利益（円）
    - min_roi: 最低ROI（％）
    - limit: 最大件数
    """
    items, total = search_prices(condition, db=db)
    return PriceResponse(items=items, total=total)
