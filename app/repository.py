# app/repository.py
from __future__ import annotations

from typing import List, Tuple, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from .db import SessionLocal
from .models import PriceSnapshot
from .schemas import PriceResult, PriceSearchCondition, PriceItem


def save_price_results(results: List[PriceResult]) -> None:
    """
    バッチやGUIから渡された PriceResult をまとめて PriceSnapshot に保存する。
    """
    if not results:
        return

    with SessionLocal() as db:
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
                diff=r.diff,
                pass_filter=r.pass_filter,
                checked_at=r.checked_at,
            )
            objects.append(obj)

        db.add_all(objects)
        db.commit()


def search_prices(
    condition: PriceSearchCondition,
    db: Optional[Session] = None,
) -> Tuple[List[PriceItem], int]:
    """
    DB から PriceSnapshot を検索して、API 用の PriceItem リスト＋総件数を返す。

    - keyword: ASIN or タイトル部分一致
    - min_profit: 最低利益（円）
    - min_roi: 最低ROI（％）
    - limit: 最大件数
    """
    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True

    try:
        q = db.query(PriceSnapshot)

        # ▼ キーワード（ASIN / タイトル の部分一致）
        if condition.keyword:
            kw = f"%{condition.keyword}%"
            q = q.filter(
                or_(
                    PriceSnapshot.asin.ilike(kw),
                    PriceSnapshot.title.ilike(kw),
                )
            )

        # ▼ 最低利益（円）
        if condition.min_profit is not None:
            q = q.filter(PriceSnapshot.profit_per_item >= condition.min_profit)

        # ▼ 最低 ROI（％）
        if condition.min_roi is not None:
            q = q.filter(PriceSnapshot.roi_percent >= condition.min_roi)

        # ▼ 件数カウント（limit かける前）
        total = q.count()

        # ▼ 並び順
        #   1. pass_filter=True を優先
        #   2. 利益が大きい順
        #   3. 新しい順
        q = (
            q.order_by(
                PriceSnapshot.pass_filter.desc(),
                PriceSnapshot.profit_per_item.desc(),
                PriceSnapshot.checked_at.desc(),
            )
            .limit(condition.limit)
        )

        rows: List[PriceSnapshot] = q.all()

        # ▼ API 用スキーマに詰め替え
        items: List[PriceItem] = [
            PriceItem(
                asin=row.asin,
                title=row.title,
                amazon_price=row.amazon_price,
                rakuten_price=row.rakuten_price,
                profit_per_item=row.profit_per_item,
                roi_percent=row.roi_percent,
                amazon_url=row.amazon_url,
                rakuten_url=row.rakuten_url,
                checked_at=row.checked_at,
            )
            for row in rows
        ]

        return items, total

    finally:
        if own_session:
            db.close()
