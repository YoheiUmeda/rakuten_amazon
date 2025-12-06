# amazon_price.py
from __future__ import annotations

import logging
from typing import List, Dict, Any

from spapi_client import get_best_amazon_price

logger = logging.getLogger(__name__)


def get_amazon_prices(asins: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Keepa で拾った ASIN リストに対して、
    SP-API から「最良オファー情報」をまとめて取得する。

    戻り値:
        {
            asin: {
                "price": float,
                "shipping": float,
                "is_fba": bool,
                "buybox": bool,
                "seller": str,
                "title": str,
                "amazon_quantity": Any,
                "amazon_price_per_item": str,
            },
            ...
        }
    """
    logger.info("[AmazonPrice] ASIN数: %d 件 → SP-API へ問い合わせ開始", len(asins))

    if not asins:
        logger.warning("[AmazonPrice] ASIN が 0 件のため、何もしません")
        return {}

    try:
        results = get_best_amazon_price(asins)
        logger.info(
            "[AmazonPrice] 取得完了: %d / %d ASIN に対してオファー情報あり",
            len(results),
            len(asins),
        )

        # 1件も取れなかったときは、一応ワーニングを出しておく
        if not results:
            logger.warning(
                "[AmazonPrice] SP-API から有効なオファーが 0 件でした "
                "(クエリ・ASINリスト・レート制限ログを確認してください)"
            )

        return results

    except Exception as e:
        # ここは「致命的エラー」扱いでログを残し、空 dict を返す
        logger.exception("[AmazonPrice] get_best_amazon_price 呼び出しでエラー: %s", e)
        return {}
