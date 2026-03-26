# app/models.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, String, DateTime, Float, Boolean
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """SQLAlchemy ベースクラス"""
    pass


class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    # ASIN（必須・インデックス）
    asin: Mapped[str] = mapped_column(
        String(20),
        index=True,
        nullable=False,
    )

    # 価格情報
    amazon_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rakuten_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # 表示用メタ情報
    title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    amazon_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    rakuten_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)

    # 粗利・ROI・フィルタフラグ
    profit_per_item: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 利益額（注文合計）
    roi_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pass_filter: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    # 取得日時（検索の基準/ソート用）
    checked_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        index=True,
        default=datetime.utcnow,
    )
