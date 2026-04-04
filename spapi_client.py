# spapi_client.py
import os
import random
import time
import logging
from datetime import datetime, timedelta

from dotenv import load_dotenv
from sp_api.api import Products, ProductFees, Catalog
from sp_api.base import Marketplaces, SellingApiException

load_dotenv(override=False)
logger = logging.getLogger(__name__)

# ========== 共通クレデンシャル ==========

def load_credentials():
    return dict(
        refresh_token     = os.getenv('REFRESH_TOKEN'),
        lwa_app_id        = os.getenv('LWA_APP_ID'),
        lwa_client_secret = os.getenv('LWA_CLIENT_SECRET'),
        aws_access_key    = os.getenv('AWS_ACCESS_KEY'),
        aws_secret_key    = os.getenv('AWS_SECRET_KEY'),
        role_arn          = os.getenv('ROLE_ARN'),
    )


# ========== Amazon Pricing（getItemOffersBatch） ==========

def get_best_amazon_price(asins):
    """
    ASIN のリストを受け取り、各 ASIN ごとの最良オファー情報の dict を返す。
    戻り値: { asin: { price, shipping, is_fba, ... }, ... }
    """
    credentials = load_credentials()
    return get_batch_pricing_info(asins, credentials)


def get_batch_pricing_info(asins, credentials):
    """
    Products.get_item_offers_batch を使って価格情報を取得。
    - レート制限: 0.1 req/sec, burst 1 (サポート回答ベース)
    - .env:
        REQUEST_UPPER_NUM: 1リクエストあたりの最大ASIN数（最大20まで使用）
        FBA_SLEEP_TIME   : リクエスト間隔（秒）※最低でも10.5秒に強制
    """
    results = {}

    # ★ Amazonサポートのレート制限に合わせて下限・上限を強制
    env_batch_size = int(os.getenv('REQUEST_UPPER_NUM', '20'))
    env_sleep_time = float(os.getenv('FBA_SLEEP_TIME', '11.5'))

    batch_size = env_batch_size if env_batch_size > 0 else 20
    batch_size = min(batch_size, 20)  # API仕様上、最大20 ASIN/リクエスト

    sleep_time = max(10.5, env_sleep_time)  # 10秒 + 余裕0.5秒

    max_retries = int(os.getenv('MAX_RETRIES', '5'))

    pp = Products(
        marketplace=Marketplaces.JP,
        credentials=credentials,
    )

    start = time.time()
    total = len(asins)

    logger.info(
        "[Pricing] config: batch_size=%d sleep_time=%.1fs max_retries=%d "
        "(env_batch_size=%d env_sleep_time=%.1fs)",
        batch_size, sleep_time, max_retries, env_batch_size, env_sleep_time
    )
    logger.info(
        "[Pricing] 開始: ASIN=%d件, batch_size=%d, sleep=%.1fs, max_retries=%d",
        total, batch_size, sleep_time, max_retries
    )

    for i in range(0, len(asins), batch_size):
        batch = asins[i:i + batch_size]
        batch_index = i // batch_size + 1

        logger.info("[Pricing] バッチ %d: %d ASIN", batch_index, len(batch))

        requests_ = [
            {
                "uri": f"/products/pricing/v0/items/{asin}/offers",
                "method": "GET",
                "ItemCondition": "New",
                "MarketplaceId": os.getenv("MARKETPLACE_ID"),
            }
            for asin in batch
        ]

        # 429/QuotaExceeded が出る前提で長めバックオフを入れる
        for attempt in range(max_retries):
            try:
                res = pp.get_item_offers_batch(requests_=requests_)

                for r in res.payload.get("responses", []):
                    asin = (
                        r.get("request", {}).get("Asin")
                        or r.get("request", {}).get("asin")
                    )
                    offers = (
                        r.get("body", {})
                        .get("payload", {})
                        .get("Offers", [])
                    )

                    buybox_offer = next(
                        (o for o in offers if o.get("IsBuyBoxWinner")), None
                    )
                    best_offer = buybox_offer or (
                        min(
                            offers,
                            key=lambda o: o.get("ListingPrice", {})
                            .get("Amount", float("inf")),
                        )
                        if offers
                        else None
                    )

                    if best_offer:
                        price = best_offer.get("ListingPrice", {}).get("Amount")
                        shipping = best_offer.get("Shipping", {}).get(
                            "Amount", 0.0
                        )
                        is_fba = (
                            best_offer.get("IsFulfilledByAmazon") is True
                            or best_offer.get("FulfillmentChannelCode")
                            in ("AMAZON_FULFILLED", "AFN")
                        )
                        buybox = best_offer.get("IsBuyBoxWinner", False)
                        seller = best_offer.get("SellerId")

                        results[asin] = {
                            "price": price,
                            "shipping": shipping,
                            "is_fba": is_fba,
                            "buybox": buybox,
                            "seller": seller,
                            "title": "",
                            "amazon_quantity": None,
                            "amazon_price_per_item": "",
                        }

                        logger.debug(
                            "[Pricing] raw offer: %s",
                            {
                                "ASIN": asin,
                                "price": price,
                                "shipping": shipping,
                                "is_fba": is_fba,
                                "buybox": buybox,
                                "seller": seller,
                            },
                        )

                logger.info(
                    "[Pricing] バッチ %d 成功 (attempt=%d)",
                    batch_index,
                    attempt + 1,
                )
                break  # このバッチは成功したのでリトライループを抜ける

            except SellingApiException as e:
                # ステータスコードとエラー詳細を引き出す
                status = getattr(
                    getattr(e, "response", None), "status_code", None
                )
                msg = str(e)
                errors = getattr(e, "errors", None)

                if status == 429 or "QuotaExceeded" in msg:
                    # ★ サポート指示に従い、429は長めのバックオフ（15秒スタート）
                    base = 15 * (attempt + 1)  # 15, 30, 45, ...
                    jitter = random.uniform(0, 5)
                    wait = base + jitter

                    logger.warning(
                        "[Pricing] Throttled/QuotaExceeded batch=%d "
                        "attempt=%d/%d code=%s errors=%s (backoff %.1fs)",
                        batch_index,
                        attempt + 1,
                        max_retries,
                        status,
                        errors,
                        wait,
                    )
                    time.sleep(wait)
                    continue  # 次の attempt へ
                else:
                    logger.error(
                        "[Pricing] API error (non-429) batch=%d attempt=%d/%d → %s",
                        batch_index,
                        attempt + 1,
                        max_retries,
                        e,
                    )
                    break  # 非429は打ち切り

            except Exception as e:
                logger.error(
                    "[Pricing] Unexpected error batch=%d attempt=%d/%d → %s",
                    batch_index,
                    attempt + 1,
                    max_retries,
                    e,
                )
                break

        eta = estimate_eta(
            start,
            batch_index - 1,
            (len(asins) + batch_size - 1) // batch_size,
        )
        logger.info("[Pricing] バッチ %d 完了 / ETA目安: %s", batch_index, eta)

        # バッチ完了ごとに最低 10.5秒以上スリープ（env値が大きければそのまま）
        time.sleep(sleep_time)

    return results


def enrich_results_with_jan(results):
    """
    現状は Keepa 側で JAN を補完しているので未使用。
    使う場合は Catalog.get_catalog_items のレスポンス構造を
    実際のJSON見ながら実装すること。
    """
    return results


# ========== FBA 手数料（既存ロジックを基本維持） ==========

def get_fba_fee(asin_price_map):
    """
    FBA手数料をASIN単位で取得（バッチ分割、休止、ETA付き）。
    """
    quota_errors = 0

    credentials = load_credentials()
    currency = os.getenv("CURRENCY", "JPY")
    marketplace_id = os.getenv("MARKETPLACE_ID")
    batch_size = int(os.getenv("REQUEST_UPPER_NUM", "10"))
    sleep_time = float(os.getenv("FBA_SLEEP_TIME", "11.5"))  # Pricing と同じ設定を再利用
    max_retries = int(os.getenv("MAX_RETRIES", "5"))

    results = {}
    asin_price_items = list(asin_price_map.items())
    total_batches = (len(asin_price_items) + batch_size - 1) // batch_size
    start_time = time.time()

    from itertools import islice

    def chunked_iter(iterable, size):
        it = iter(iterable)
        while True:
            chunk = list(islice(it, size))
            if not chunk:
                break
            yield chunk

    for batch_index, batch in enumerate(chunked_iter(asin_price_items, batch_size)):
        estimate_requests = []

        for asin, item in batch:
            try:
                price = float(item["price"])
                shipping = float(item.get("shipping", 0.0))
                is_fba = bool(item.get("is_fba"))

                estimate_requests.append(
                    {
                        "id_type": "ASIN",
                        "id_value": asin,
                        "price": price,
                        "currency": currency,
                        "shipping_price": shipping,
                        "is_fba": is_fba,
                        "marketplace_id": marketplace_id,
                        "identifier": asin,
                    }
                )
            except Exception as e:
                logger.error("[FBA] データエラー ASIN=%s: %s", asin, e)
                results[asin] = {
                    "fee": None,
                    "fee_raw": [],
                    "error": str(e),
                }

        pf = ProductFees(marketplace=Marketplaces.JP, credentials=credentials)

        for attempt in range(max_retries):
            try:
                response = pf.get_product_fees_estimate(estimate_requests)

                for estimate in response.payload:
                    asin = (
                        estimate.get("FeesEstimateIdentifier", {}).get("IdValue")
                    )
                    fee_details = (
                        estimate.get("FeesEstimate", {}).get("FeeDetailList", [])
                    )
                    total_fee = sum(
                        [
                            fee.get("FinalFee", {}).get("Amount", 0.0)
                            for fee in fee_details
                        ]
                    )

                    results[asin] = {
                        "fee": total_fee,
                        "fee_raw": fee_details,
                    }

                    logger.info(
                        "[✅ FBA手数料取得] ASIN=%s 手数料=%.2f円",
                        asin,
                        total_fee,
                    )

                logger.info(
                    "[FBA] batch=%d/%d 手数料取得成功",
                    batch_index + 1,
                    total_batches,
                )
                break

            except Exception as e:
                msg = str(e)
                if "QuotaExceeded" in msg:
                    quota_errors += 1
                    base = min(60, 2 ** attempt)
                    jitter = random.uniform(0, base)
                    wait = base + jitter
                    logger.warning(
                        "[FBA] QuotaExceeded batch=%d retry=%d/%d → wait %.1fs",
                        batch_index + 1,
                        attempt + 1,
                        max_retries,
                        wait,
                    )
                    time.sleep(wait)
                else:
                    logger.error(
                        "[FBA] API通信エラー（Quota以外） batch=%d → %s",
                        batch_index + 1,
                        e,
                    )
                    break

        else:
            logger.error(
                "[FBA] 最大リトライ超過 batch_index=%d → スキップ",
                batch_index,
            )
            for asin, _ in batch:
                results[asin] = {
                    "fee": None,
                    "fee_raw": [],
                    "error": "QuotaExceeded or API Error",
                }

        eta = estimate_eta(start_time, batch_index, total_batches)
        logger.info(
            "[FBA] 進捗: %d/%d バッチ完了 | ETA: %s",
            batch_index + 1,
            total_batches,
            eta,
        )
        time.sleep(sleep_time)

    logger.info(
        "[FBA] QuotaExceeded 発生回数: %d 回 / バッチ数: %d",
        quota_errors,
        total_batches,
    )
    return results


# ========== 共通ヘルパー ==========

def estimate_eta(start_time: float, index: int, total: int) -> str:
    elapsed = time.time() - start_time
    rate = elapsed / (index + 1)
    remaining = (total - (index + 1)) * rate
    eta_time = datetime.now() + timedelta(seconds=remaining)
    return eta_time.strftime("%Y-%m-%d %H:%M:%S")


def chunked(iterable, size):
    """イテラブルを size 件ずつ分割するヘルパー関数"""
    for i in range(0, len(iterable), size):
        yield iterable[i : i + size]


# ========== 単体テスト用エントリポイント ==========

if __name__ == "__main__":
    # ログ設定（ターミナル＋標準ログ用）
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

    print("=== spapi_client main start ===")

    creds = load_credentials()
    logger.info("REFRESH_TOKEN set: %s", bool(creds["refresh_token"]))
    logger.info("LWA_APP_ID set: %s", bool(creds["lwa_app_id"]))
    logger.info("LWA_CLIENT_SECRET set: %s", bool(creds["lwa_client_secret"]))
    logger.info("AWS_ACCESS_KEY set: %s", bool(creds["aws_access_key"]))
    logger.info("AWS_SECRET_KEY set: %s", bool(creds["aws_secret_key"]))
    logger.info("ROLE_ARN set: %s", bool(creds["role_arn"]))

    # env から見た設定値の確認
    env_batch_size = os.getenv("REQUEST_UPPER_NUM")
    env_sleep_time = os.getenv("FBA_SLEEP_TIME")
    logger.info("ENV REQUEST_UPPER_NUM=%s", env_batch_size)
    logger.info("ENV FBA_SLEEP_TIME=%s", env_sleep_time)

    test_asin = ["B0056DUNLW"]  # 適当なASINに変えてOK

    try:
        res = get_best_amazon_price(test_asin)
        logger.info("get_best_amazon_price OK. result: %s", res)
    except SellingApiException as e:
        logger.error("SellingApiException: %s", e)
    except Exception as e:
        logger.error("Other Exception: %s", e)
