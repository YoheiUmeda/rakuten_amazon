# app/api/prices.py
from __future__ import annotations

from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import PriceSnapshot
from app.schemas import PriceSnapshotResponse

router = APIRouter(prefix="/api/prices", tags=["prices"])


# DBセッションをFastAPI用にラップ
def get_db():
    with get_session() as db:
        yield db


@router.get("/", response_model=List[PriceSnapshotResponse])
def list_prices(
    # 🔍 絞り込み用パラメータ
    asin: Optional[str] = Query(
        None, description="特定ASINで絞り込み（完全一致）"
    ),
    keyword: Optional[str] = Query(
        None, description="商品タイトルの部分一致キーワード"
    ),
    since: Optional[datetime] = Query(
        None, description="この日時以降にチェックされたデータに限定"
    ),
    min_profit: float = Query(
        0, ge=0, description="最低利益（円）。0なら無条件"
    ),
    min_roi: float = Query(
        0, ge=0, description="最低ROI（%）。0なら無条件"
    ),
    only_passed: bool = Query(
        False, description="Trueなら pass_filter=True のレコードのみ"
    ),
    limit: int = Query(
        200, ge=1, le=1000, description="最大取得件数"
    ),
    sort_by: str = Query(
        "checked_at",
        description="ソート基準: checked_at / profit / roi / diff",
    ),
    sort_dir: str = Query(
        "desc",
        description="ソート方向: asc / desc",
    ),
    db: Session = Depends(get_db),
):
    """
    price_snapshots を絞り込み＆ソートして取得するAPI。
    """

    # ベースクエリ
    stmt = select(PriceSnapshot)
    conditions = []

    # ---- 絞り込み条件を積む ----
    if asin:
        conditions.append(PriceSnapshot.asin == asin)

    if keyword:
        # 部分一致（PostgreSQLなので ilike でOK）
        like = f"%{keyword}%"
        conditions.append(PriceSnapshot.title.ilike(like))

    if since:
        conditions.append(PriceSnapshot.checked_at >= since)

    if min_profit > 0:
        conditions.append(PriceSnapshot.profit_per_item >= min_profit)

    if min_roi > 0:
        conditions.append(PriceSnapshot.roi_percent >= min_roi)

    if only_passed:
        conditions.append(PriceSnapshot.pass_filter.is_(True))

    if conditions:
        stmt = stmt.where(*conditions)

    # ---- ソート条件 ----
    sort_map = {
        "checked_at": PriceSnapshot.checked_at,
        "profit": PriceSnapshot.profit_per_item,
        "roi": PriceSnapshot.roi_percent,
        "diff": PriceSnapshot.diff,
    }
    sort_col = sort_map.get(sort_by, PriceSnapshot.checked_at)

    if sort_dir == "asc":
        stmt = stmt.order_by(sort_col.asc())
    else:
        stmt = stmt.order_by(sort_col.desc())

    # ---- limit ----
    stmt = stmt.limit(limit)

    # ---- 実行 ----
    result = db.execute(stmt).scalars().all()
    return result
