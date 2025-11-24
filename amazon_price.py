# amazon_price.py
from __future__ import annotations

from typing import Dict, Any, List
import logging

from spapi_client import get_best_amazon_price
from keepa_client import enrich_results_with_keepa_jan

logger = logging.getLogger(__name__)


def get_amazon_prices(asins: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    ASINリストを受け取り、SP-API と Keepa を使って
    Amazonの価格情報＋JAN等の詳細を付与して返す。

    戻り値:
        { ASIN: { price, shipping, is_fba, jan, title, ... }, ... }
    """
    if not asins:
        logger.info("[AmazonPrice] 入力ASINが0件のためスキップ")
        return {}

    logger.info(f"[AmazonPrice] SP-API 価格取得開始: {len(asins)} ASIN")

    # 1️⃣ SP-APIで最良オファーを取得
    amazon_data = get_best_amazon_price(asins)
    logger.info(f"[AmazonPrice] SP-API 価格取得完了: {len(amazon_data)} ASIN")

    if not amazon_data:
        logger.warning("[AmazonPrice] SP-API結果が空 → 後続処理スキップ")
        return {}

    # 2️⃣ KeepaでJAN・販売数など詳細情報を enrich
    logger.info("[AmazonPrice] Keepa 詳細情報付与開始 (JAN / 販売数 / 数量 等)")
    enriched = enrich_results_with_keepa_jan(amazon_data)
    logger.info(f"[AmazonPrice] Keepa 詳細情報付与完了: {len(enriched)} ASIN")

    return enriched
