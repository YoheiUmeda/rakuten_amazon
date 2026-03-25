# amazon_fee.py
from __future__ import annotations

import csv
import logging
import os
from typing import Any, Dict, Optional

from dotenv import load_dotenv

from spapi_client import get_fba_fee

load_dotenv(override=True)

logger = logging.getLogger(__name__)

# デフォルトのFBA配送手数料（サイズ情報が取れないときのフォールバック）
DEFAULT_FBA_SHIPPING_FEE = 485


def get_amazon_fees_estimate(
    asin_price_map: Dict[str, Dict[str, Any]]
) -> Dict[str, Dict[str, Any]]:
    """
    SP-API から FBA 手数料を取得し、asin_price_map に
    fee / total_fee / fba_shipping_fee を付加して返す。
    """
    results = get_fba_fee(asin_price_map)
    return annotate_fees_to_asin_price_map(asin_price_map, results)


# 1. CSV 読み込み（Amazon公式手数料表をパース）
def load_fba_fee_table(path: Optional[str] = None) -> list[Dict[str, int | str]]:
    """
    Amazon FBA手数料CSVをファイルから読み込む。

    path:
        相対パス or 絶対パス。
        指定がなければ .env の FBA_FEE_TABLE_PATH か 'data/fba_fee_table.csv' を使う。
    """
    rel_path = path or os.getenv("FBA_FEE_TABLE_PATH", "data/fba_fee_table.csv")

    # このファイル (amazon_fee.py) を基準にした絶対パス
    base_dir = os.path.dirname(os.path.abspath(__file__))
    abs_path = os.path.join(base_dir, rel_path)

    if not os.path.exists(abs_path):
        raise FileNotFoundError(
            f"[ERROR] FBA手数料ファイルが見つかりません: {abs_path}\n"
            f"現在のカレントディレクトリ: {os.getcwd()}"
        )

    fee_table: list[Dict[str, int | str]] = []

    with open(abs_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            fee_table.append(
                {
                    "サイズ区分": row["サイズ区分"],
                    "重量上限": int(row["重量グラム上限"]),
                    "手数料": int(row["手数料"]),
                }
            )

    logger.info(f"[FBA Fee] 手数料テーブル読込: {len(fee_table)} 行 ({abs_path})")
    return fee_table


# 2. 梱包サイズ（cm）と重量（g）から Amazon サイズ区分を判定
def get_size_category_by_dimensions(
    weight_g: Optional[int], dimensions_cm: Optional[list[float]]
) -> str:
    """
    重量(g)と 3辺(cm) からサイズ区分を推定する。
    想定: [長辺, 中辺, 短辺] だが、ソートして判定しているので順番は不問。
    """
    if not dimensions_cm or len(dimensions_cm) != 3 or weight_g is None:
        # 情報足りない場合は標準扱い
        return "標準"

    length, width, height = sorted(dimensions_cm, reverse=True)
    weight_kg = weight_g / 1000

    if length <= 60 and width <= 35 and height <= 3 and weight_kg <= 0.25:
        return "小型"
    if length <= 60 and width <= 45 and height <= 35 and weight_kg <= 1.0:
        return "標準"
    if length <= 80 and width <= 60 and height <= 50 and weight_kg <= 9:
        return "大型1"
    if length <= 140 and width <= 60 and height <= 60 and weight_kg <= 15:
        return "大型2"
    return "超大型"


# 3. サイズ区分と重さに応じて CSV から配送手数料を取得
def estimate_fba_shipping_fee_by_dimensions(
    weight_g: Optional[int],
    dimensions_cm: Optional[list[float]],
    fee_table: list[Dict[str, int | str]],
) -> int:
    """
    サイズ情報と fee_table から FBA 配送手数料を推定。
    情報が足りない場合や該当行が無い場合は DEFAULT_FBA_SHIPPING_FEE を返す。
    """
    if weight_g is None:
        return DEFAULT_FBA_SHIPPING_FEE

    category = get_size_category_by_dimensions(weight_g, dimensions_cm)

    for fee_entry in fee_table:
        if (
            fee_entry["サイズ区分"] == category
            and weight_g <= int(fee_entry["重量上限"])
        ):
            return int(fee_entry["手数料"])

    return DEFAULT_FBA_SHIPPING_FEE


# 4. メイン処理：拡張版 annotate_fees_to_asin_price_map
def annotate_fees_to_asin_price_map(
    asin_price_map: Dict[str, Dict[str, Any]],
    results: Any,
    size_db: Optional[Dict[str, Dict[str, Any]]] = None,
    fee_table_path: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    SP-API から取得した手数料情報 (results) を asin_price_map にマージし、
    fee / fee_raw / fba_shipping_fee / total_fee を付与して返す。

    results:
        - list形式: get_product_fees_estimate の生 payload に近いもの
        - dict形式: { asin: { fee, fee_raw, ... }, ... }
    size_db:
        - { asin: { "dimensions_cm": [L, W, H], "weight_g": 123 }, ... }
        - 省略時は DEFAULT_FBA_SHIPPING_FEE を使用
    """
    fee_table = load_fba_fee_table(fee_table_path)
    enriched: Dict[str, Dict[str, Any]] = {asin: data.copy() for asin, data in asin_price_map.items()}

    def apply_shipping_fee(asin: str) -> int:
        """
        サイズ情報があればそこから FBA 配送手数料を推定。
        無ければフォールバック値を返す。
        """
        if size_db and asin in size_db:
            dims = size_db[asin].get("dimensions_cm")
            weight = size_db[asin].get("weight_g")
            return estimate_fba_shipping_fee_by_dimensions(weight, dims, fee_table)

        return DEFAULT_FBA_SHIPPING_FEE

    # パターン1: SP-APIそのままの list 形式
    if isinstance(results, list):
        for item in results:
            if not isinstance(item, dict):
                logger.warning("[FBA Fee] unexpected item skipped: %r", item)
                continue

            asin = item.get("FeesEstimateIdentifier", {}).get("IdValue")
            status = item.get("Status")

            if not asin or asin not in enriched:
                continue

            if status == "Success":
                fee = (
                    item.get("FeesEstimate", {})
                    .get("TotalFeesEstimate", {})
                    .get("Amount")
                )

                enriched[asin]["fee"] = fee
                enriched[asin]["fee_raw"] = item.get("FeesEstimate", {}).get(
                    "FeeDetailList", []
                )

                shipping_fee = apply_shipping_fee(asin)
                enriched[asin]["fba_shipping_fee"] = shipping_fee
                enriched[asin]["total_fee"] = (fee + shipping_fee) if fee is not None else None
            else:
                logger.warning("[FBA Fee] ASIN=%s Status=%s → feeなし", asin, status)
                enriched[asin]["fee"] = None
                enriched[asin]["fee_raw"] = []
                enriched[asin]["fba_shipping_fee"] = None
                enriched[asin]["total_fee"] = None

    # パターン2: { ASIN: { fee, fee_raw, ... } } 形式
    elif isinstance(results, dict):
        for asin, item in results.items():
            if asin not in enriched:
                continue

            fee = item.get("fee")
            enriched[asin]["fee"] = fee
            enriched[asin]["fee_raw"] = item.get("fee_raw", [])

            shipping_fee = apply_shipping_fee(asin)
            enriched[asin]["fba_shipping_fee"] = shipping_fee
            enriched[asin]["total_fee"] = (fee + shipping_fee) if fee is not None else None

    else:
        logger.error(
            "[FBA Fee] annotate_fees_to_asin_price_map: results は list または dict である必要があります (type=%s)",
            type(results),
        )

    return enriched
