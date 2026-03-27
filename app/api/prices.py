# app/api/prices.py
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy import and_, case, func
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import PriceSnapshot
from app.schemas import PriceItem, PriceSearchCondition, PriceResponse, PriceSummary

router = APIRouter()


@router.get("/prices/summary", response_model=PriceSummary)
def get_price_summary(db: Session = Depends(get_db)) -> PriceSummary:
    """全ASIN・最新件の集計サマリーを返す。"""
    latest_sq = (
        db.query(func.max(PriceSnapshot.id).label("max_id"))
        .group_by(PriceSnapshot.asin)
        .subquery()
    )
    row = (
        db.query(
            func.count(PriceSnapshot.id).label("count"),
            func.max(PriceSnapshot.checked_at).label("latest"),
            func.avg(PriceSnapshot.profit_per_item).label("avg_profit"),
            func.avg(PriceSnapshot.roi_percent).label("avg_roi"),
        )
        .join(latest_sq, PriceSnapshot.id == latest_sq.c.max_id)
        .one()
    )
    return PriceSummary(
        latest_checked_at=row.latest,
        count=row.count or 0,
        avg_profit=row.avg_profit,
        avg_roi=row.avg_roi,
    )


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
        if cond.pass_min_profit is not None or cond.pass_min_roi is not None:
            if cond.pass_min_profit is not None:
                q = q.filter(PriceSnapshot.profit_per_item >= cond.pass_min_profit)
            if cond.pass_min_roi is not None:
                q = q.filter(PriceSnapshot.roi_percent >= cond.pass_min_roi)
        else:
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

    # 並び順：仕入候補を先頭に、その中で利益の大きい順、同じなら新しい順
    if cond.pass_min_profit is not None or cond.pass_min_roi is not None:
        _conds = []
        if cond.pass_min_profit is not None:
            _conds.append(PriceSnapshot.profit_per_item >= cond.pass_min_profit)
        if cond.pass_min_roi is not None:
            _conds.append(PriceSnapshot.roi_percent >= cond.pass_min_roi)
        _pass_expr = case((and_(*_conds), 1), else_=0)
        q = q.order_by(
            _pass_expr.desc(),
            PriceSnapshot.profit_per_item.desc().nullslast(),
            PriceSnapshot.checked_at.desc(),
        )
    else:
        q = q.order_by(
            PriceSnapshot.pass_filter.desc().nullslast(),
            PriceSnapshot.profit_per_item.desc().nullslast(),
            PriceSnapshot.checked_at.desc(),
        )

    # limit が指定されていれば適用（schemas のデフォルトを 1000 にしておくと安心）
    if cond.limit:
        q = q.limit(cond.limit)

    rows: List[PriceSnapshot] = q.all()

    def _pass(r: PriceSnapshot):
        if cond.pass_min_profit is None and cond.pass_min_roi is None:
            return r.pass_filter
        profit_ok = cond.pass_min_profit is None or (
            r.profit_per_item is not None and r.profit_per_item >= cond.pass_min_profit
        )
        roi_ok = cond.pass_min_roi is None or (
            r.roi_percent is not None and r.roi_percent >= cond.pass_min_roi
        )
        return profit_ok and roi_ok

    items: List[PriceItem] = [
        PriceItem(
            asin=r.asin,
            title=(r.title or ""),
            amazon_price=r.amazon_price,
            rakuten_price=r.rakuten_price,
            profit_per_item=r.profit_per_item,
            roi_percent=r.roi_percent,
            pass_filter=_pass(r),
            checked_at=r.checked_at,
            amazon_url=r.amazon_url,
            rakuten_url=r.rakuten_url,
        )
        for r in rows
    ]

    # total は「絞り込み後・limit前」の件数
    return PriceResponse(items=items, total=total)
