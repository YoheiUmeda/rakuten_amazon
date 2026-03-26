# app/schemas.py
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


# ----------------------------
# バッチ → DB 保存用
# ----------------------------
class PriceResult(BaseModel):
    """バッチ処理で計算した 1 商品分のスナップショット。"""

    asin: str
    title: str

    amazon_url: Optional[str] = None
    rakuten_url: Optional[str] = None

    amazon_price: Optional[float] = None   # Amazon 側の価格（SP-API ListingPrice、注文合計額）
    rakuten_price: Optional[float] = None  # 採用した楽天の実質仕入れ額（合計、ポイント控除後）

    profit_per_item: Optional[float] = None  # 利益額（注文合計）
    roi_percent: Optional[float] = None      # 利回り（％）

    pass_filter: bool = False                # 仕入候補フラグ
    checked_at: datetime                     # スナップショット取得日時（UTC）


# ----------------------------
# FastAPI リクエスト／レスポンス用
# ----------------------------
class PriceSearchCondition(BaseModel):
    """
    ダッシュボード検索条件。
    条件を指定しなければ、その項目では絞り込みなし。
    """

    keyword: Optional[str] = None       # ASIN or タイトルの部分一致
    min_profit: Optional[float] = None  # 最低利益（円）
    min_roi: Optional[float] = None     # 最低 ROI（％）
    limit: int = 1000                   # ★ デフォルト 1000件
    only_pass_filter: bool = False      # True なら pass_filter=True のみ

class PriceItem(BaseModel):
    asin: str
    title: str

    amazon_price: Optional[float] = None
    rakuten_price: Optional[float] = None  # 採用した楽天の実質仕入れ額（合計、ポイント控除後）

    profit_per_item: Optional[float] = None  # 利益額（注文合計）
    roi_percent: Optional[float] = None

    checked_at: datetime                # いつチェックしたか

    amazon_url: Optional[str] = None
    rakuten_url: Optional[str] = None


class PriceResponse(BaseModel):
    """価格一覧 API のレスポンス。"""

    items: List[PriceItem]
    total: int
