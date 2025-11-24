# scripts/debug_db.py
from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

# プロジェクトルート: .../rakuten_amazon
BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# .env 読み込み（DATABASE_URL など）
env_path = BASE_DIR / ".env"
if env_path.exists():
    load_dotenv(env_path, override=True)
else:
    # カレントに .env がある場合などのフォールバック
    load_dotenv(override=True)

from app.db import SessionLocal
from app.models import PriceSnapshot


def main() -> None:
    with SessionLocal() as db:
        total = db.query(PriceSnapshot).count()
        print("Total rows:", total)

        rows = (
            db.query(PriceSnapshot)
            .order_by(PriceSnapshot.checked_at.desc())
            .limit(10)
            .all()
        )

        for r in rows:
            print(
                r.id,
                r.asin,
                (r.title or "")[:30],
                r.amazon_price,
                r.rakuten_price,
                r.profit_per_item,
                r.roi_percent,
                r.pass_filter,
            )


if __name__ == "__main__":
    main()
