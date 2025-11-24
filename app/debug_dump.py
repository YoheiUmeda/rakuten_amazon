# app/debug_dump.py
from __future__ import annotations

from .db import get_session
from .models import Product, PriceSnapshot


def main() -> None:
    with get_session() as session:
        print("=== Products (最大10件) ===")
        products = session.query(Product).order_by(Product.id.asc()).limit(10).all()
        for p in products:
            print(f"[Product] id={p.id}, asin={p.asin}, title={p.title}")

        print("\n=== Latest PriceSnapshots (最大20件) ===")
        snapshots = (
            session.query(PriceSnapshot)
            .order_by(PriceSnapshot.checked_at.desc())
            .limit(20)
            .all()
        )
        for s in snapshots:
            print(
                f"[Snap] id={s.id}, product_id={s.product_id}, "
                f"at={s.checked_at}, "
                f"amazon={s.amazon_price}, rakuten={s.rakuten_price}, diff={s.diff}"
            )


if __name__ == "__main__":
    main()
