# app/api/prices.py
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy import func
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
    """
    価格一覧検索 API

    - デフォルトでは「全スナップショット」を対象にする
    - keyword / min_profit / min_roi / only_pass_filter が指定されたときだけ絞り込む
    - limit で最大件数を制御（schemas側のデフォルトを 1000 にしておく）
    """

    # ★ ここがポイント：
    #   以前は「最新実行分だけ」を対象にしていたが、
    #   いまは DB 全体（全スナップショット）を対象にする。
    q = db.query(PriceSnapshot)

    # キーワード（タイトル or ASIN 部分一致）
    if cond.keyword:
        like = f"%{cond.keyword}%"
        q = q.filter(
            (PriceSnapshot.title.ilike(like))
            | (PriceSnapshot.asin.ilike(like))
        )

    # pass_filter フラグでの絞り込み
    if cond.only_pass_filter:
        q = q.filter(PriceSnapshot.pass_filter.is_(True))

    # 利益／ROI 下限
    if cond.min_profit is not None:
        q = q.filter(PriceSnapshot.profit_per_item >= cond.min_profit)

    if cond.min_roi is not None:
        q = q.filter(PriceSnapshot.roi_percent >= cond.min_roi)

    # ASIN ごとに最新1件だけ残す（id が最大 = 最後に挿入された行）
    latest_sq = (
        db.query(func.max(PriceSnapshot.id).label("max_id"))
        .group_by(PriceSnapshot.asin)
        .subquery()
    )
    q = q.join(latest_sq, PriceSnapshot.id == latest_sq.c.max_id)

    # 件数（limit をかける前の総件数）
    total = q.count()

    # 並び順：デフォルトは「利益の大きい順、同じなら新しい順」
    q = q.order_by(
        PriceSnapshot.profit_per_item.desc().nullslast(),
        PriceSnapshot.checked_at.desc(),
    )

    # limit が指定されていれば適用（schemas のデフォルトを 1000 にしておくと安心）
    if cond.limit:
        q = q.limit(cond.limit)

    rows: List[PriceSnapshot] = q.all()

    items: List[PriceItem] = [
        PriceItem(
            asin=r.asin,
            title=(r.title or ""),
            amazon_price=r.amazon_price,
            rakuten_price=r.rakuten_price,
            profit_per_item=r.profit_per_item,
            roi_percent=r.roi_percent,
            pass_filter=r.pass_filter,
            checked_at=r.checked_at,
            amazon_url=r.amazon_url,
            rakuten_url=r.rakuten_url,
        )
        for r in rows
    ]

    # total は「絞り込み後・limit前」の件数
    return PriceResponse(items=items, total=total)
