# app/schemas.py
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


# ----------------------------------------
# バッチ → DB 保存用（1レコード単位）
# ----------------------------------------
class PriceResult(BaseModel):
    """
    バッチ処理で計算した 1 商品分のスナップショット。
    DB の PriceSnapshot にそのままマッピングされる前提。
    """

    asin: str
    # バッチ側で "" にフォールバックしているので必須 str で運用
    title: str

    amazon_url: Optional[str] = None
    rakuten_url: Optional[str] = None

    # Amazon 側の価格（総額 or 1個あたり、どちらでもOK）
    amazon_price: Optional[float] = None
    # 採用した楽天の 1 個あたり原価
    rakuten_price: Optional[float] = None

    # 1個あたり利益（= Amazon受取額/個 - 楽天原価/個）
    profit_per_item: Optional[float] = None
    # 利回り（％）。例: 20% → 20.0
    roi_percent: Optional[float] = None
    # 価格差（使わない場合は None でOK）
    diff: Optional[float] = None

    # 仕入候補としてフィルタを通過したかどうか
    pass_filter: bool = False

    # スナップショット取得日時（UTC）
    checked_at: datetime


# ----------------------------------------
# FastAPI のリクエスト／レスポンス用
# ----------------------------------------
class PriceSearchCondition(BaseModel):
    """
    ダッシュボード検索条件。
    条件を指定しなければ、その項目では絞り込みなし。
    """

    keyword: Optional[str] = None       # ASIN or タイトルの部分一致
    min_profit: Optional[float] = None  # 最低利益（円）
    min_roi: Optional[float] = None     # 最低 ROI（％）
    limit: int = 50                     # 最大件数


class PriceItem(BaseModel):
    """
    画面に返す 1 商品分の情報。
    """
    asin: str
    title: str

    amazon_price: Optional[float] = None
    rakuten_price: Optional[float] = None

    profit_per_item: Optional[float] = None
    roi_percent: Optional[float] = None

    # いつチェックしたデータか（JSON では ISO8601 文字列）
    checked_at: datetime

    amazon_url: Optional[str] = None
    rakuten_url: Optional[str] = None


class PriceResponse(BaseModel):
    """
    価格一覧 API のレスポンス。
    total は条件に合致した件数の総数（ページングしたければここから使う）。
    """

    items: List[PriceItem]
    total: int
