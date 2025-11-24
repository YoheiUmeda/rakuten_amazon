# app/schemas.py
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


# ----------------------------------------
# バッチ → DB 保存で使う用
# ----------------------------------------
class PriceResult(BaseModel):
    asin: str
    title: str

    amazon_url: Optional[str] = None
    rakuten_url: Optional[str] = None

    amazon_price: Optional[float] = None   # Amazon側の価格（総額 or 1個あたり、どちらでもOK）
    rakuten_price: Optional[float] = None  # 採用した楽天の1個あたり原価

    profit_per_item: Optional[float] = None  # 1個あたり利益
    roi_percent: Optional[float] = None      # 利回り（％）
    diff: Optional[float] = None             # 価格差（使わなければ None でOK）

    pass_filter: bool = False                # フィルタ通過フラグ
    checked_at: datetime                     # 取得日時


# ----------------------------------------
# FastAPI のリクエスト／レスポンス用
# ----------------------------------------
class PriceSearchCondition(BaseModel):
    keyword: Optional[str] = None      # ASIN or タイトルに対する部分一致
    min_profit: Optional[float] = None # 最低利益（円）。指定なしなら絞り込み無し
    min_roi: Optional[float] = None    # 最低ROI（％）。指定なしなら絞り込み無し
    limit: int = 50                    # 最大件数


class PriceItem(BaseModel):
    asin: str
    title: str

    amazon_price: Optional[float] = None
    rakuten_price: Optional[float] = None

    profit_per_item: Optional[float] = None
    roi_percent: Optional[float] = None

    amazon_url: Optional[str] = None
    rakuten_url: Optional[str] = None


class PriceResponse(BaseModel):
    items: List[PriceItem]
    total: int
