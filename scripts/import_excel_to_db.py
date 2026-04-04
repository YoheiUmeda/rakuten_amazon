# scripts/import_excel_to_db.py
"""
Excel出力ファイルをDBにインポートするスクリプト。
バッチ実行時にDB接続失敗した場合の後から投入用。

使い方:
  venv/Scripts/python scripts/import_excel_to_db.py output/20260404142013_pf_jp_no_amazon_rank15k_4k15k_v1.xlsx
"""
from __future__ import annotations

import sys
import logging
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv
load_dotenv(override=True)

import openpyxl
from app.schemas import PriceResult
from app.repository import save_price_results
from excel_exporter import HEADER_MAP_JA as _EXCEL_HEADER_MAP

# ExcelヘッダJA→フィールドのマッピング（excel_exporter.py HEADER_MAP_JA の逆引き）
# import field → excel_exporter.py 内部キー の対応表
_IMPORT_FIELD_TO_EXPORTER_KEY = {
    "asin":            "ASIN",
    "title":           "title",
    "amazon_price":    "price",
    "rakuten_price":   "rakuten_effective_cost_1",
    "profit_per_item": "profit_per_item",
    "roi_percent":     "roi_percent",
    "pass_filter":     "pass_filter",
    "rakuten_url":     "rakuten_url_1",
}

_JA_TO_KEY = {
    "ASIN": "asin",
    "商品タイトル": "title",
    "Amazon価格": "amazon_price",
    "楽天仕入額(1)": "rakuten_price",
    "利益/個（参考）": "profit_per_item",
    "利益率(%)": "roi_percent",
    "フィルタ通過": "pass_filter",
    "楽天URL(1)": "rakuten_url",
}


def _validate_header_mapping() -> None:
    """_JA_TO_KEY の各列について、HEADER_MAP_JA[exporter_key] == ja_label を検証する。"""
    mismatches = []
    for ja_label, import_field in _JA_TO_KEY.items():
        exporter_key = _IMPORT_FIELD_TO_EXPORTER_KEY.get(import_field)
        if exporter_key is None:
            mismatches.append(f"{import_field!r}: _IMPORT_FIELD_TO_EXPORTER_KEY に未定義")
            continue
        actual = _EXCEL_HEADER_MAP.get(exporter_key)
        if actual != ja_label:
            mismatches.append(
                f"{import_field!r}: HEADER_MAP_JA[{exporter_key!r}]={actual!r}, 期待={ja_label!r}"
            )
    if mismatches:
        raise ValueError("HEADER_MAP_JA との不一致:\n" + "\n".join(mismatches))


def _to_float(v) -> float | None:
    try:
        return float(v) if v is not None and v != "" else None
    except (ValueError, TypeError):
        return None


def _to_bool(v) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in ("true", "1", "yes")
    return bool(v) if v else False


def load_excel(path: Path) -> list[PriceResult]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise ValueError("Excelが空です")

    headers = [str(h) if h is not None else "" for h in rows[0]]
    col_idx = {}
    for ja, key in _JA_TO_KEY.items():
        if ja in headers:
            col_idx[key] = headers.index(ja)

    required = {"asin"}
    missing = required - col_idx.keys()
    if missing:
        raise ValueError(f"必須列が見つかりません: {missing}\nヘッダ: {headers[:10]}")

    checked_at = datetime.now(tz=timezone.utc)
    results: list[PriceResult] = []

    for row in rows[1:]:
        asin = row[col_idx["asin"]] if "asin" in col_idx else None
        if not asin:
            continue

        results.append(PriceResult(
            asin=str(asin),
            title=str(row[col_idx["title"]]) if "title" in col_idx and row[col_idx["title"]] else "",
            amazon_price=_to_float(row[col_idx["amazon_price"]]) if "amazon_price" in col_idx else None,
            rakuten_price=_to_float(row[col_idx["rakuten_price"]]) if "rakuten_price" in col_idx else None,
            profit_per_item=_to_float(row[col_idx["profit_per_item"]]) if "profit_per_item" in col_idx else None,
            roi_percent=_to_float(row[col_idx["roi_percent"]]) if "roi_percent" in col_idx else None,
            pass_filter=_to_bool(row[col_idx["pass_filter"]]) if "pass_filter" in col_idx else False,
            rakuten_url=str(row[col_idx["rakuten_url"]]) if "rakuten_url" in col_idx and row[col_idx["rakuten_url"]] else None,
            amazon_url=f"https://www.amazon.co.jp/dp/{asin}",
            checked_at=checked_at,
        ))

    wb.close()
    return results


def main():
    _validate_header_mapping()
    if len(sys.argv) < 2:
        print("使い方: python scripts/import_excel_to_db.py <Excelファイルパス>")
        sys.exit(1)

    excel_path = Path(sys.argv[1])
    if not excel_path.is_absolute():
        excel_path = BASE_DIR / excel_path

    if not excel_path.exists():
        logger.error("ファイルが見つかりません: %s", excel_path)
        sys.exit(1)

    logger.info("読み込み開始: %s", excel_path)
    results = load_excel(excel_path)
    logger.info("読み込み完了: %d 件", len(results))

    save_price_results(results)
    logger.info("DB保存完了: %d 件", len(results))


if __name__ == "__main__":
    main()
