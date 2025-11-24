# batch_runner.py
from __future__ import annotations

import logging
import os
import time
from datetime import datetime
from typing import List, Dict, Any

from dotenv import load_dotenv

from prefilter import prefilter_for_rakuten
from keepa_client import get_asins_from_finder
from amazon_fee import get_amazon_fees_estimate
from amazon_price import get_amazon_prices
from rakuten_client import get_rakuten_info
from price_calculation import calculate_price_difference
from excel_exporter import export_asin_dict_to_excel

from app.schemas import PriceResult
from app.repository import save_price_results


# .env 読み込み（CLI から直接呼ばれたとき用）
load_dotenv(override=True)

MIN_PROFIT_YEN = int(os.getenv("MIN_PROFIT_YEN", "700"))
MIN_ROI_PERCENT = float(os.getenv("MIN_ROI_PERCENT", "15"))


def run_batch_once(query: str, logger: logging.Logger | None = None) -> None:
    """
    GUI なしで 1 回分のバッチを実行する。
    - Keepa Product Finder クエリを受け取り
    - SP-API / Rakuten / FBA手数料を叩き
    - 価格差を計算
    - Excel と DB に保存する
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    start_time = time.time()
    logger.info("[BATCH] ===== 開始 =====")
    logger.info(f"[BATCH] Query: {query[:200]}...")

    # 1️⃣ ASIN リスト取得（Keepa Product Finder）
    asins: List[str] = get_asins_from_finder(query)
    n_asins = len(asins)

    if not asins:
        logger.warning("[BATCH] ASIN取得 0件（もしくは失敗） → 処理終了")
        return

    elapsed = time.time() - start_time
    logger.info(f"[1/4] ASIN取得完了: {n_asins}件 (経過 {elapsed:.1f}秒)")

    # 2️⃣ Amazon価格＋FBA手数料
    logger.info("[BATCH] Amazon価格取得中...")
    amazon_offer_data: Dict[str, Dict[str, Any]] = get_amazon_prices(asins)

    logger.info("[BATCH] FBA手数料取得中...")
    amazon_offer_data_with_fee: Dict[str, Dict[str, Any]] = get_amazon_fees_estimate(
        amazon_offer_data
    )

    elapsed = time.time() - start_time
    logger.info(
        f"[2/4] Amazon価格＋手数料取得完了 "
        f"(ASIN: {len(amazon_offer_data_with_fee)}件, 経過 {elapsed:.1f}秒)"
    )

    # 3️⃣ 楽天検索用プレフィルタ
    logger.info("[BATCH] 楽天検索候補の事前絞り込み中...")
    filtered_for_rakuten: Dict[str, Dict[str, Any]] = prefilter_for_rakuten(
        amazon_offer_data_with_fee,
        min_max_possible_profit=1500,
        min_price=3000,
    )
    n_filtered = len(filtered_for_rakuten)

    elapsed = time.time() - start_time
    logger.info(
        f"[3/4] 楽天検索対象: {n_filtered}件 / 元ASIN: {len(amazon_offer_data_with_fee)}件 "
        f"(経過 {elapsed:.1f}秒)"
    )

    if not filtered_for_rakuten:
        logger.info("[BATCH] 楽天検索対象が 0件 のため終了")
        return

    # 3.5️⃣ 楽天価格取得
    logger.info("[BATCH] 楽天価格情報取得中...")
    amazon_offer_data_with_fee_rakuten: Dict[str, Dict[str, Any]] = get_rakuten_info(
        filtered_for_rakuten
    )

    elapsed = time.time() - start_time
    logger.info(f"[3.5/4] 楽天価格情報取得完了 (経過 {elapsed:.1f}秒)")

    # 4️⃣ 価格差計算
    logger.info("[BATCH] 価格差計算中...")
    target_result: Dict[str, Dict[str, Any]] = calculate_price_difference(
        amazon_offer_data_with_fee_rakuten
    )
    n_final = len(target_result)

    if target_result:
        sample_asin, sample_data = next(iter(target_result.items()))
        logger.info(f"[BATCH DEBUG] SAMPLE asin={sample_asin}, data={sample_data}")

    # 4.5️⃣ DB 保存用オブジェクト組み立て
    price_results: List[PriceResult] = []

    for asin, data in target_result.items():
        title = data.get("title") or ""
        amazon_url = data.get("amazon_url") or ""
        rakuten_url = data.get("rakuten_url") or data.get("rakuten_url_1")

        amazon_price_raw = data.get("price")
        rakuten_price_raw = data.get("rakuten_effective_cost_per_item_selected")

        amazon_received_per_item = data.get("amazon_received_per_item")
        rakuten_cost_selected = data.get("rakuten_effective_cost_per_item_selected")

        profit_per_item = data.get("profit_per_item")
        if (
            profit_per_item is None
            and amazon_received_per_item is not None
            and rakuten_cost_selected is not None
        ):
            profit_per_item = float(amazon_received_per_item) - float(
                rakuten_cost_selected
            )

        roi_percent = data.get("roi_percent")
        if roi_percent is None:
            profit_rate = data.get("profit_rate")
            if profit_rate is not None:
                roi_percent = float(profit_rate) * 100.0
            elif profit_per_item is not None and rakuten_cost_selected:
                base = float(rakuten_cost_selected)
                if base > 0:
                    roi_percent = profit_per_item / base * 100.0

        diff = data.get("price_diff_after_point")
        if diff is None:
            diff = data.get("price_diff")

        pass_filter = (
            profit_per_item is not None
            and roi_percent is not None
            and profit_per_item >= MIN_PROFIT_YEN
            and roi_percent >= MIN_ROI_PERCENT
        )

        price_results.append(
            PriceResult(
                asin=asin,
                title=title,
                amazon_url=amazon_url,
                rakuten_url=rakuten_url,
                amazon_price=float(amazon_price_raw)
                if amazon_price_raw is not None
                else None,
                rakuten_price=float(rakuten_price_raw)
                if rakuten_price_raw is not None
                else None,
                profit_per_item=float(profit_per_item)
                if profit_per_item is not None
                else None,
                roi_percent=float(roi_percent) if roi_percent is not None else None,
                diff=float(diff) if diff is not None else None,
                pass_filter=pass_filter,
                checked_at=datetime.utcnow(),
            )
        )

    # 5️⃣ DB へ一括保存
    if price_results:
        logger.info(f"[BATCH] DB へ {len(price_results)} 件保存中...")
        save_price_results(price_results)

    # 既存の Excel 出力もそのまま残す
    excel_path = export_asin_dict_to_excel(target_result)
    elapsed = time.time() - start_time

    logger.info(
        "[SUMMARY] 元ASIN: %d件 / 楽天検索対象: %d件 / 価格差候補: %d件",
        len(amazon_offer_data),
        len(filtered_for_rakuten),
        len(target_result),
    )

    logger.info(
        f"[4/4] 価格差候補: {n_final}件, Excel出力: {excel_path or 'なし'} "
        f"/ 総処理時間: {elapsed:.1f}秒"
    )
    logger.info("[BATCH] ===== 終了 =====")
