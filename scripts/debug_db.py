# scripts/debug_db.py

import os
import sys
from dotenv import load_dotenv

# ▼ プロジェクトルートを sys.path に追加
BASE_DIR = os.path.dirname(os.path.abspath(__file__))          # .../rakuten_amazon/scripts
PROJECT_ROOT = os.path.dirname(BASE_DIR)                       # .../rakuten_amazon

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ▼ .env 読み込み（DATABASE_URL など）
env_path = os.path.join(PROJECT_ROOT, ".env")
if os.path.exists(env_path):
    load_dotenv(env_path, override=True)

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
