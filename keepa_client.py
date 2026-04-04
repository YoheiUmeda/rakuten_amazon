# keepa_client.py
from __future__ import annotations

import json
import urllib.parse
import logging
import os
import time
import urllib.parse
from typing import Dict, Any, Iterable, List

import requests
from dotenv import load_dotenv

_KEEPA_TIMEOUT = (10, 30)  # (connect_timeout, read_timeout) 秒

from utils.utils import extract_quantity_combined

load_dotenv(override=False)
logger = logging.getLogger(__name__)


def get_asins_from_finder(query_jsonstr: str) -> list[str]:
    """
    Keepa Product Finder のクエリ文字列（URL想定）から selection を抽出し、
    Keepa Query API で ASIN を取得してフラットなリストで返す。
    """
    api_key = os.getenv("KEEPA_API_KEY")
    url = "https://api.keepa.com/query"

    if not api_key:
        logger.error("[Keepa] KEEPA_API_KEY が未設定のため ASIN 取得不可")
        return []

    # selection 部分をパース
    selection = parse_json(query_jsonstr)
    if not selection:
        logger.warning("[Keepa] selection が空または不正のため ASIN 取得をスキップ")
        return []

    # ENV で指定された最小販売速度を selection に注入（未設定・0 の場合は無効）
    try:
        _min_drops = int(os.getenv("KEEPA_FINDER_MIN_DROPS30", "0") or "0")
    except (ValueError, TypeError):
        _min_drops = 0
    if _min_drops > 0 and "salesRankDrops30Min" not in selection:
        selection["salesRankDrops30Min"] = _min_drops

    logger.info("[Keepa] Product Finder クエリ開始")
    logger.debug("[Keepa] selection=%s", selection)

    params = {"key": api_key, "domain": 5, "selection": json.dumps(selection)}

    try:
        r = requests.get(url, params=params, timeout=_KEEPA_TIMEOUT)
        logger.debug("[Keepa] Request URL: %s", r.url)
        logger.debug(
            "[Keepa] Status: %s, Body preview: %s",
            r.status_code,
            r.text[:500],
        )

        r.raise_for_status()
        data = r.json()
    except Exception as e:
        logger.error("[Keepa] Product Finder API エラー: %s", e)
        return []

    asins = data.get("asinList", [])
    flat_asins: list[str] = []

    for item in asins:
        if isinstance(item, list):
            flat_asins.extend(item)
        else:
            flat_asins.append(item)

    logger.info("[Keepa] ASIN取得完了: %d件", len(flat_asins))
    return flat_asins


def enrich_results_with_keepa_jan(
    results: Dict[str, Dict[str, Any]],
    wait_time: float = 0.5,
) -> Dict[str, Dict[str, Any]]:
    """
    Keepa APIを使って、ASINごとのJAN・ブランド・モデル・販売推定数などを results に付加する。

    priority:
      monthly_sold > salesRankDrops30 > 推定（csv, 30日間ごと）
    """
    asins = list(results.keys())
    api_key = os.getenv("KEEPA_API_KEY")
    request_upper = int(os.getenv("KEEPA_REQUEST_UPPER_NUM", "10"))

    if not api_key:
        logger.error("[Keepa] KEEPA_API_KEY 未設定のため enrich をスキップ")
        return results

    logger.info(
        "[Keepa] 詳細JAN/販売数 enrich 開始: %d ASIN, バッチ上限=%d",
        len(asins),
        request_upper,
    )

    for idx, batch in enumerate(chunks(asins, request_upper), start=1):
        logger.info("[Keepa] バッチ %d: ASIN %d件", idx, len(batch))

        url = (
            "https://api.keepa.com/product"
            f"?key={api_key}&domain=5&asin={','.join(batch)}&history=1"
        )

        try:
            res = requests.get(url, timeout=_KEEPA_TIMEOUT)
            res.raise_for_status()
            data = res.json()

            for product in data.get("products", []):
                asin = product.get("asin")
                if asin not in results:
                    continue

                ean_list = product.get("eanList", [])
                title = (product.get("title") or "").strip()
                brand = (product.get("brand") or "").strip()
                model = (product.get("model") or "").strip()
                features = product.get("features") or []
                description = (product.get("description") or "").strip()

                quantity = (
                    extract_quantity_combined(title)
                    or next(
                        (
                            extract_quantity_combined(bp)
                            for bp in features
                            if extract_quantity_combined(bp)
                        ),
                        None,
                    )
                    or extract_quantity_combined(description)
                    or 1  # 最後のフォールバック
                )

                if not model:
                    model = (product.get("partNumber") or "").strip()

                jan = (
                    str(ean_list[0])
                    if ean_list
                    else str(product.get("ean"))
                    if product.get("ean")
                    else None
                )

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
                        estimated_monthly_sold_30 = estimate_sales_from_rank_history(
                            keepa_rank_history, 0, 30, keepa_time_now
                        )
                        estimated_monthly_sold_60 = estimate_sales_from_rank_history(
                            keepa_rank_history, 30, 60, keepa_time_now
                        )
                        estimated_monthly_sold_90 = estimate_sales_from_rank_history(
                            keepa_rank_history, 60, 90, keepa_time_now
                        )
                        estimated_monthly_sold = estimated_monthly_sold_30

                # --- 結果登録
                results[asin].update(
                    {
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
                    }
                )

            time.sleep(wait_time)

        except Exception as e:
            logger.error("[Keepaエラー] batch=%s → %s", batch, e)
            for asin in batch:
                if asin in results:
                    results[asin].update(
                        {
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
                        }
                    )

    logger.debug("[Keepa] enrich_results sample: %s", list(results.items())[:3])
    return results


def estimate_sales_from_rank_history(
    rank_history: List[int],
    days_from: int,
    days_to: int,
    keepa_time_now: int | None = None,
) -> int:
    """
    Keepa の rank history（csv[3]）から [days_from, days_to] の期間の
    想定販売個数をざっくり推定する。
    """
    min_jump = int(os.getenv("KEEPA_RANK_HISTORY_MIN_JUMP", "1000"))
    min_minutes = int(os.getenv("KEEPA_RANK_HISTORY_MIN_MINUTES", "720"))

    if not rank_history or len(rank_history) < 4:
        return 0

    if keepa_time_now is None:
        keepa_time_now = rank_history[-2]

    time_start = keepa_time_now - days_to * 24 * 60
    time_end = keepa_time_now - days_from * 24 * 60

    count = 0
    last_counted_time = -1_000_000_000_000_000  # 十分小さい値
    prev_rank = None

    for i in range(0, len(rank_history) - 2, 2):
        t0, r0 = rank_history[i], rank_history[i + 1]
        t1, r1 = rank_history[i + 2], rank_history[i + 3]

        if not (time_start <= t1 < time_end):
            continue

        # ジャンプ判定＋一定時間経過条件
        if (
            prev_rank is not None
            and (r1 < prev_rank)
            and ((prev_rank - r1) >= min_jump)
            and (t1 - last_counted_time >= min_minutes)
        ):
            count += 1
            last_counted_time = t1

        prev_rank = r1

    return count


def parse_json(query_str: str):
    """
    Product Finder の selection を返す。
    - 生の JSON（{"foo": ...}）でも
    - Keepa の共有URL（...?selection=...）でもOK。
    """
    query_str = (query_str or "").strip()
    if not query_str:
        return {}

    # 1) まず「生JSON」として試す
    try:
        obj = json.loads(query_str)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    # 2) ダメなら URL とみなして selection= を拾う
    parsed_url = urllib.parse.urlparse(query_str)
    params = urllib.parse.parse_qs(parsed_url.query)
    encoded_selection = params.get("selection", [None])[0]

    if not encoded_selection:
        print("selection パラメータが見つかりませんでした。")
        return {}

    try:
        decoded_selection = urllib.parse.unquote(encoded_selection)
        selection_dict = json.loads(decoded_selection)
        return selection_dict
    except json.JSONDecodeError as e:
        print(f"selection JSON のパースに失敗しました: {e}")
        return {}

def chunks(lst: list[str], size: int) -> Iterable[list[str]]:
    """ASINリストを size 件ずつのチャンクに分ける"""
    for i in range(0, len(lst), size):
        yield lst[i : i + size]
