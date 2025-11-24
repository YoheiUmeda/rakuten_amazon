# app/debug_import_test.py
from __future__ import annotations

from .db import get_session
from .models import Product
from .repository import save_price_results


def main() -> None:
    print("get_session:", get_session)
    print("Product model:", Product)
    print("save_price_results:", save_price_results)
    print("Imports OK")


if __name__ == "__main__":
    main()
