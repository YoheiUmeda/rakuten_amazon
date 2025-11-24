# spapi_client.py
import os
import random
import time
from dotenv import load_dotenv
from sp_api.api import Products, ProductFees, Catalog
from sp_api.base import Marketplaces
import logging

load_dotenv(override=True)
logger = logging.getLogger(__name__)

credentials = dict(
    refresh_token      = os.getenv('REFRESH_TOKEN'),
    lwa_app_id         = os.getenv('LWA_APP_ID'),
    lwa_client_secret  = os.getenv('LWA_CLIENT_SECRET'),
    aws_access_key     = os.getenv('AWS_ACCESS_KEY'),
    aws_secret_key     = os.getenv('AWS_SECRET_KEY'),
    role_arn           = os.getenv('ROLE_ARN')
)

def get_best_amazon_price(asins):
    """
    ASINのリストを受け取り、各ASINごとの最良オファー情報の dict を返す。
    戻り値: { asin: { price, shipping, is_fba, ... }, ... }
    """
    credentials = load_credentials()
    return get_batch_pricing_info(asins, credentials)

def get_batch_pricing_info(asins, credentials):
    results = {}
    pp = Products(
        marketplace=Marketplaces.JP,
        credentials=credentials
    )

    sleep_time = float(os.getenv('FBA_SLEEP_TIME', '2.5'))  # default: 2.5秒
    batch_size = int(os.getenv('REQUEST_UPPER_NUM', '3'))  # API上限
    max_retries = int(os.getenv('MAX_RETRIES', '3'))        # リトライ上限
    start = time.time()
    total = len(asins)

    logger.info(
        f"[Pricing] 開始: ASIN={len(asins)}件, "
        f"batch_size={batch_size}, sleep={sleep_time}s, max_retries={max_retries}"
    )
    
    for i in range(0, len(asins), batch_size):
        batch = asins[i:i + batch_size]
        batch_index = i // batch_size + 1

        logger.info(f"[Pricing] バッチ {batch_index}: {len(batch)} ASIN")

        requests_ = [
            {
                'uri': f'/products/pricing/v0/items/{asin}/offers',
                'method': 'GET',
                'ItemCondition': 'New',
                'MarketplaceId': os.getenv('MARKETPLACE_ID')
            } for asin in batch
        ]

        success = False

        for attempt in range(max_retries):
            try:
                res = pp.get_item_offers_batch(requests_=requests_)

                for r in res.payload.get('responses', []):
                    asin = r.get('request', {}).get('Asin') or r.get('request', {}).get('asin')
                    offers = r.get('body', {}).get('payload', {}).get('Offers', [])
                    buybox_offer = next((o for o in offers if o.get('IsBuyBoxWinner')), None)
                    best_offer = buybox_offer or (
                        min(offers, key=lambda o: o.get('ListingPrice', {}).get('Amount', float('inf')))
                        if offers else None
                    )

                    if best_offer:
                        price = best_offer.get('ListingPrice', {}).get('Amount')
                        shipping = best_offer.get('Shipping', {}).get('Amount', 0)
                        is_fba = (
                            best_offer.get('IsFulfilledByAmazon') is True or
                            best_offer.get('FulfillmentChannelCode') in ('AMAZON_FULFILLED', 'AFN')
                        )
                        buybox = best_offer.get('IsBuyBoxWinner', False)
                        seller = best_offer.get('SellerId')

                        results[asin] = {
                            'price': price,
                            'shipping': shipping,
                            'is_fba': is_fba,
                            'buybox': buybox,
                            'seller': seller,
                            'title': '',
                            'amazon_quantity': None,
                            'amazon_price_per_item': '',
                        }

                        print({
                            'ASIN': asin,
                            'price': price,
                            'shipping': shipping,
                            'is_fba': is_fba,
                            'buybox': buybox,
                            'seller': seller
                        })

                logger.info(f"[Pricing] バッチ {batch_index} 成功 (attempt={attempt+1})")
                success = True
                break

            except Exception as e:
                base = min(60, (2 ** attempt))
                jitter = random.uniform(0, base)
                wait = base + jitter
                logger.warning(
                    f"[Pricing] API error batch={batch_index} attempt={attempt+1}/{max_retries} → {e} "
                    f"(backoff {wait:.1f}s)"
                )
                if attempt < max_retries - 1:
                    time.sleep(wait)
                else:
                    logger.error(f"[Pricing] 最大リトライ超過 → スキップ batch={batch}")

        eta = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(
            start + ((total // batch_size) * sleep_time)
        ))
        logger.info(f"[Pricing] バッチ {batch_index} 完了 / ETA目安: {eta}")
        time.sleep(sleep_time)

    return results

def enrich_results_with_jan(results):
    """
    現状は Keepa 側で JAN を補完しているので未使用。
    使う場合は Catalog.get_catalog_items のレスポンス構造を
    実際のJSON見ながら実装すること。
    """
    return results

# def enrich_results_with_jan(results):
#     """
#     results (dict): ASINをキーにした辞書に JAN を追記する
#     Returns:
#         dict: jan を追加した results
#     """
#     credentials = load_credentials()
#     marketplace_id = os.getenv('MARKETPLACE_ID')
#     batch_size = int(os.getenv('REQUEST_UPPER_NUM', '10'))
#     sleep_time = float(os.getenv('FBA_SLEEP_TIME', '1.5'))
#     max_retries = int(os.getenv('MAX_RETRIES', '3'))

#     catalog = Catalog(marketplace=Marketplaces.JP, credentials=credentials)
#     start = time.time()
#     asins = list(results.keys())

#     for bi, batch in enumerate(chunked(asins, batch_size)):
#         success = False
#         for attempt in range(max_retries):
#             try:
#                 response = catalog.get_catalog_items(
#                     identifiers=batch,
#                     marketplaceIds=marketplace_id
#                 )
#                 items = response.payload.get("items", [])
#                 for item in items:
#                     identifiers = item.get("identifiers", {})
#                     jan = identifiers.get("jan") or identifiers.get("ean") or None
#                     if asin in results:
#                         results[asin]["jan"] = jan
#                 success = True
#                 break  # 成功したら retry 抜ける

#             except Exception as e:
#                 # ✅ Exponential Backoff + Full Jitter
#                 base = min(60, 2 ** attempt)
#                 jitter = random.uniform(0, base)
#                 wait = base + jitter

#                 print(f"[❌ JAN取得エラー] batch_index={bi} attempt={attempt + 1}/{max_retries} → {e}")
#                 if attempt < max_retries - 1:
#                     print(f"🔁 バックオフ：{wait:.1f}秒待機（base={base}, jitterあり）")
#                     time.sleep(wait)
#                 else:
#                     print(f"🚫 最大リトライ超過 → スキップ batch={batch}")
#                     for asin in batch:
#                         results[asin]["jan"] = None

#         eta = estimate_eta(start, bi, len(asins) // batch_size)
#         print(f"[JAN] {bi+1}/{(len(asins) - 1) // batch_size + 1}バッチ完了 / ETA: {eta}")
#         time.sleep(sleep_time)

#     return results

#region FBAデータ取得
def get_fba_fee(asin_price_map):
    """
    FBA手数料をASIN単位で取得（バッチ分割、休止、ETA付き）。
    """
    quota_errors = 0

    credentials = load_credentials()
    currency = os.getenv('CURRENCY', 'JPY')
    marketplace_id = os.getenv('MARKETPLACE_ID')
    batch_size = int(os.getenv('REQUEST_UPPER_NUM', '10'))
    sleep_time = float(os.getenv('FBA_SLEEP_TIME', '1.5'))  # default: 1.5秒
    max_retries = int(os.getenv('MAX_RETRIES', '3'))

    results = {}
    asin_price_items = list(asin_price_map.items())
    total_batches = (len(asin_price_items) + batch_size - 1) // batch_size
    start_time = time.time()

    for batch_index, batch in enumerate(chunked(asin_price_items, batch_size)):
        estimate_requests = []

        for asin, item in batch:
            try:
                price = float(item['price'])
                shipping = float(item.get('shipping', 0.0))
                is_fba = bool(item.get('is_fba'))

                estimate_requests.append({
                    "id_type": "ASIN",
                    "id_value": asin,
                    "price": price,
                    "currency": currency,
                    "shipping_price": shipping,
                    "is_fba": is_fba,
                    "marketplace_id": marketplace_id,
                    "identifier": asin,
                })
            except Exception as e:
                print(f"[❌ データエラー] ASIN={asin}: {e}")
                results[asin] = {"fee": None, "fee_raw": [], "error": str(e)}

        pf = ProductFees(marketplace=Marketplaces.JP, credentials=credentials)

        for attempt in range(max_retries):
            try:
                response = pf.get_product_fees_estimate(estimate_requests)

                for estimate in response.payload:
                    asin = estimate.get("FeesEstimateIdentifier", {}).get("IdValue")
                    fee_details = estimate.get("FeesEstimate", {}).get("FeeDetailList", [])
                    total_fee = sum([
                        fee.get("FinalFee", {}).get("Amount", 0.0)
                        for fee in fee_details
                    ])

                    results[asin] = {
                        "fee": total_fee,
                        "fee_raw": fee_details
                    }

                    print(f"[✅ FBA手数料取得] ASIN={asin} 手数料={total_fee:.2f}円")

                logger.info(f"[FBA] batch={batch_index+1}/{total_batches} 手数料取得成功")
                break

            except Exception as e:
                if "QuotaExceeded" in str(e):
                    quota_errors += 1
                    base = min(60, 2 ** attempt)
                    jitter = random.uniform(0, base)
                    wait = base + jitter
                    logger.warning(
                        f"[FBA] QuotaExceeded batch={batch_index+1} retry={attempt+1}/{max_retries} "
                        f"→ wait {wait:.1f}s (base={base:.1f}+jitter)"
                    )
                    time.sleep(wait)
                else:
                    logger.error(f"[FBA] API通信エラー（Quota以外） batch={batch_index+1} → {e}")
                    break

        else:
            print(f"[🚫 最大リトライ超過] batch_index={batch_index} → スキップ")
            for asin, _ in batch:
                results[asin] = {
                    "fee": None,
                    "fee_raw": [],
                    "error": "QuotaExceeded or API Error"
                }

        eta = estimate_eta(start_time, batch_index, total_batches)
        logger.info(f"[FBA] 進捗: {batch_index + 1}/{total_batches} バッチ完了 | ETA: {eta}")
        time.sleep(sleep_time)

    logger.info(f"[FBA] QuotaExceeded 発生回数: {quota_errors} 回 / バッチ数: {total_batches}")
    return results
#end region

from datetime import datetime, timedelta
import time

def estimate_eta(start_time: float, index: int, total: int) -> str:
    elapsed = time.time() - start_time
    rate = elapsed / (index + 1)
    remaining = (total - (index + 1)) * rate
    eta_time = datetime.now() + timedelta(seconds=remaining)
    return eta_time.strftime('%Y-%m-%d %H:%M:%S')

#helper method
def chunked(iterable, size):
    """イテラブルをsize件ずつ分割するヘルパー関数"""
    for i in range(0, len(iterable), size):
        yield iterable[i:i + size]

def load_credentials():
    return dict(
        refresh_token      = os.getenv('REFRESH_TOKEN'),
        lwa_app_id         = os.getenv('LWA_APP_ID'),
        lwa_client_secret  = os.getenv('LWA_CLIENT_SECRET'),
        aws_access_key     = os.getenv('AWS_ACCESS_KEY'),
        aws_secret_key     = os.getenv('AWS_SECRET_KEY'),
        role_arn           = os.getenv('ROLE_ARN')
    )

# spapi_client.py の一番下あたり

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(override=True)

    creds = load_credentials()
    print("REFRESH_TOKEN set:", bool(creds["refresh_token"]))
    print("LWA_APP_ID set:", bool(creds["lwa_app_id"]))
    print("LWA_CLIENT_SECRET set:", bool(creds["lwa_client_secret"]))
    print("AWS_ACCESS_KEY set:", bool(creds["aws_access_key"]))
    print("AWS_SECRET_KEY set:", bool(creds["aws_secret_key"]))
    print("ROLE_ARN set:", bool(creds["role_arn"]))

    # ついでに 1 ASIN だけ叩いてみるテスト
    test_asin = ["B0056DUNLW"]  # 適当なASINに変えてOK
    from sp_api.base import SellingApiException
    try:
        res = get_best_amazon_price(test_asin)
        print("API call OK. result:", res)
    except SellingApiException as e:
        print("SellingApiException:", e)
    except Exception as e:
        print("Other Exception:", e)
