# get_keepa_prices.py
from __future__ import annotations

import logging
import os
from typing import Dict, Any, List

import requests
from dotenv import load_dotenv

load_dotenv(override=True)
logger = logging.getLogger(__name__)


def get_latest_valid_price(csv_data: List[int | None] | None) -> int | None:
    """
    Keepa CSV配列から「直近の有効な価格」を取得する。
    csv_data: [time0, price0, time1, price1, ...] の形。
    """
    if not csv_data or len(csv_data) < 2:
        return None

    # 後ろから time/price のペアを見ていく
    for i in range(len(csv_data) - 1, 0, -2):
        price = csv_data[i]
        if price is not None and price != -1:
            return price

    return None


def get_keepa_summary(asins: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Keepa Product API から、指定 ASIN 群の
    - BuyBox 新品 or マーケットプレイス新品の最新価格
    - FBA かどうか
    をまとめて取得する簡易ユーティリティ。

    戻り値:
        {
          ASIN: {
            "amz_price": int | None,  # keepa形式の価格（100で割る前）
            "is_fba": bool,
          },
          ...
        }
    """
    api_key = os.getenv("KEEPA_API_KEY")
    if not api_key:
        logger.error("[Keepa] KEEPA_API_KEY が未設定のため価格取得不可")
        return {}

    url = "https://api.keepa.com/product"
    headers = {"Accept-Encoding": "gzip"}

    # ※ 元コードでは domain=6。挙動を変えないためそのまま維持。
    domain = int(os.getenv("KEEPA_DOMAIN", "6"))

    results: Dict[str, Dict[str, Any]] = {}

    if not asins:
        logger.info("[Keepa] ASINが空のため処理スキップ")
        return results

    logger.info("[Keepa] 価格サマリ取得開始: %d ASIN", len(asins))

    # 最大100ASINまとめてリクエスト可
    for i in range(0, len(asins), 100):
        batch = asins[i : i + 100]
        params = {
            "key": api_key,
            "domain": domain,
            "asin": ",".join(batch),
            "buybox": 1,
            "stats": 1,
            "history": 1,
        }

        try:
            r = requests.get(url, params=params, headers=headers)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            logger.error("[Keepa] Product API エラー batch=%s → %s", batch, e)
            continue

        products = data.get("products", [])
        logger.debug("[Keepa] batch=%d, products=%d", i // 100 + 1, len(products))

        for p in products:
            asin = p.get("asin")
            if not asin:
                continue

            fba = p.get("fbaFees") is not None

            csv_list = p.get("csv") or []

            # BuyBox新品: index=10, マーケットプレイス新品: index=1
            bb_csv = csv_list[10] if len(csv_list) > 10 else None
            np_csv = csv_list[1] if len(csv_list) > 1 else None

            bb_price = get_latest_valid_price(bb_csv)
            np_price = get_latest_valid_price(np_csv)

            price = bb_price if bb_price is not None else np_price

            results[asin] = {
                "amz_price": price,
                "is_fba": bool(fba),
            }

    logger.info("[Keepa] 価格サマリ取得完了: %d件", len(results))
    return results
