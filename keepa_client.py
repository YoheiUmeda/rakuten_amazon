import requests
import os
import json
import urllib.parse
from utils.utils import extract_quantity_combined
from dotenv import load_dotenv

import logging

logger = logging.getLogger(__name__)
load_dotenv(override=True)

def get_asins_from_finder(query_jsonstr):
    api_key = os.getenv('KEEPA_API_KEY')
    url = 'https://api.keepa.com/query'

    # selection 部分をパース
    selection = parse_json(query_jsonstr)
    if not selection:
        logger.warning("[Keepa] selection が空または不正のため ASIN 取得をスキップ")
        return {}

    logger.info("[Keepa] Product Finder クエリ開始")
    logger.debug(f"[Keepa] selection={selection}")

    params = {'key': api_key, 'domain': 5, 'selection': json.dumps(selection)}

    try:
        r = requests.get(url, params=params)
        logger.debug(f"[Keepa] Request URL: {r.url}")
        logger.debug(f"[Keepa] Status: {r.status_code}, Body preview: {r.text[:500]}")

        r.raise_for_status()
        data = r.json()
    except Exception as e:
        logger.error(f"[Keepa] Product Finder API エラー: {e}")
        return {}

    asins = data.get('asinList', [])
    flat_asins = []
    for item in asins:
        if isinstance(item, list):
            flat_asins.extend(item)
        else:
            flat_asins.append(item)

    logger.info(f"[Keepa] ASIN取得完了: {len(flat_asins)}件")
    return flat_asins

def enrich_results_with_keepa_jan(results, wait_time=0.5):
    """
    Keepa APIを使って、ASINごとのJAN・ブランド・モデル・販売推定数などをresultsに付加する。
    priority: monthly_sold > salesRankDrops30 > 推定（csv, 30日間ごと）
    """
    import os, time, requests

    asins = list(results.keys())
    api_key = os.getenv('KEEPA_API_KEY')
    request_upper = int(os.getenv('KEEPA_REQUEST_UPPER_NUM', '10'))

    logger.info(f"[Keepa] 詳細JAN/販売数 enrich 開始: {len(asins)} ASIN, バッチ上限={request_upper}")

    for idx, batch in enumerate(chunks(asins, request_upper), start=1):
        logger.info(f"[Keepa] バッチ {idx}: ASIN {len(batch)}件")
        url = (
            "https://api.keepa.com/product"
            f"?key={api_key}&domain=5&asin={','.join(batch)}&history=1"
        )
        try:
            res = requests.get(url)
            res.raise_for_status()
            data = res.json()

            for product in data.get("products", []):
                asin = product.get("asin")
                if asin not in results:
                    continue

                ean_list = product.get("eanList", [])
                title    = (product.get("title") or "").strip()
                brand    = (product.get("brand") or "").strip()
                model    = (product.get("model") or "").strip()
                features = product.get("features") or []
                description = (product.get("description") or "").strip()
                quantity = (
                    extract_quantity_combined(title)
                    or next((extract_quantity_combined(bp) for bp in features if extract_quantity_combined(bp)), None)
                    or extract_quantity_combined(description)
                    or 1  # 最後のフォールバック
                )
                if not model:
                    model = (product.get('partNumber') or "").strip()
                jan = str(ean_list[0]) if ean_list else str(product.get("ean")) if product.get("ean") else None
                sales_rank_drops = product.get("salesRankDrops30")
                sales_ranks = product.get("salesRanks", {}).get("SALES", [])
                monthly_sold = product.get("monthlySold")
                csv = product.get("csv", [])

                # --- 全カラム初期化
                estimated_monthly_sold = None
                estimated_monthly_sold_30 = None
                estimated_monthly_sold_60 = None
                estimated_monthly_sold_90 = None

                # --- 推定ロジック本体
                if monthly_sold is not None:
                    estimated_monthly_sold = monthly_sold
                elif sales_rank_drops is not None:
                    estimated_monthly_sold = sales_rank_drops
                elif isinstance(csv, list) and len(csv) > 3 and isinstance(csv[3], list):
                    keepa_rank_history = csv[3]
                    if len(keepa_rank_history) >= 4:
                        keepa_time_now = keepa_rank_history[-2]
                        estimated_monthly_sold_30 = estimate_sales_from_rank_history(keepa_rank_history, 0, 30, keepa_time_now)
                        estimated_monthly_sold_60 = estimate_sales_from_rank_history(keepa_rank_history, 30, 60, keepa_time_now)
                        estimated_monthly_sold_90 = estimate_sales_from_rank_history(keepa_rank_history, 60, 90, keepa_time_now)
                        estimated_monthly_sold    = estimated_monthly_sold_30
                # else: 全てNoneのまま

                # --- 結果登録
                results[asin].update({
                    "jan": jan,
                    "title": title,
                    "brand": brand,
                    "model": model,
                    "salesrank_drops30": sales_rank_drops,
                    "monthly_sold": monthly_sold,
                    "estimated_monthly_sold": estimated_monthly_sold,
                    "estimated_monthly_sold_30": estimated_monthly_sold_30,
                    "estimated_monthly_sold_60": estimated_monthly_sold_60,
                    "estimated_monthly_sold_90": estimated_monthly_sold_90,
                    "keepa_salesranks": sales_ranks,
                    "amazon_quantity": quantity,
                })
            time.sleep(wait_time)
        except Exception as e:
            logger.error(f"[Keepaエラー] batch={batch} → {e}")
            for asin in batch:
                if asin in results:
                    results[asin].update({
                        "jan": None,
                        "title": None,
                        "brand": None,
                        "model": None,
                        "salesrank_drops30": None,
                        "monthly_sold": None,
                        "estimated_monthly_sold": None,
                        "estimated_monthly_sold_30": None,
                        "estimated_monthly_sold_60": None,
                        "estimated_monthly_sold_90": None,
                        "keepa_salesranks": None,
                        "amazon_quantity": None,
                    })
        print(results)
    return results

def estimate_sales_from_rank_history(
    rank_history, days_from, days_to, keepa_time_now=None):
    
    min_jump = int(os.getenv('KEEPA_RANK_HISTORY_MIN_JUMP',1000))
    min_minutes = int(os.getenv('KEEPA_RANK_HISTORY_MIN_MINUTES',720))

    if not rank_history or len(rank_history) < 4:
        return 0
    if keepa_time_now is None:
        keepa_time_now = rank_history[-2]
    time_start = keepa_time_now - days_to * 24 * 60
    time_end   = keepa_time_now - days_from * 24 * 60

    count = 0
    last_counted_time = -1e15
    prev_rank = None
    prev_time = None
    for i in range(0, len(rank_history)-2, 2):
        t0, r0 = rank_history[i], rank_history[i+1]
        t1, r1 = rank_history[i+2], rank_history[i+3]
        if not (time_start <= t1 < time_end):
            continue
        # ジャンプ判定＋12h経過条件
        if prev_rank is not None and (r1 < prev_rank) and ((prev_rank - r1) >= min_jump) and (t1 - last_counted_time >= min_minutes):
            count += 1
            last_counted_time = t1
        prev_rank = r1
    return count

def parse_json(query__jsonstr):
       # URLをパースして selection パラメータを取り出す
    parsed_url = urllib.parse.urlparse(query__jsonstr)
    params = urllib.parse.parse_qs(parsed_url.query)

    # "selection" の値はリストで返るので [0] で取り出す
    encoded_selection = params.get("selection", [None])[0]

    if encoded_selection:
        # %xx を普通の文字に戻す（URL decode）
        decoded_selection = urllib.parse.unquote(encoded_selection)

        # JSONを辞書に変換
        selection_dict = json.loads(decoded_selection)

        # 表示
        import pprint
        pprint.pprint(selection_dict)
        return selection_dict
    else:
        print("selection パラメータが見つかりませんでした。")
        return {}
    
def chunks(lst, size):
    """ASINリストをsize件ずつのチャンクに分ける"""
    for i in range(0, len(lst), size):
        yield lst[i:i + size]