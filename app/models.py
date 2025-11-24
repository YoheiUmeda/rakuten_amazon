# app/models.py
from __future__ import annotations

from datetime import datetime
from typing import List
from typing import Optional

from sqlalchemy import (
    Integer,
    String,
    DateTime,
    Float,
    Boolean,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass

class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 🔽 今回エラーになっている asin カラムをちゃんと定義
    asin: Mapped[str] = mapped_column(String(20), index=True, nullable=False)

    # 最低限の数値カラム
    amazon_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rakuten_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    diff: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # 追加で持っておきたい情報（タイトルやURL）
    title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    amazon_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    rakuten_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)

    profit_per_item: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    roi_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pass_filter: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    checked_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, index=True, default=datetime.utcnow
    )