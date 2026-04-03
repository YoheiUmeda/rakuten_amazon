# batch_runner.py
from __future__ import annotations

import logging
import os
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
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

logger = logging.getLogger(__name__)

# ★ root ロガー初期化（FastAPI 経由でも [BATCH] ログが出るようにする）
root_logger = logging.getLogger()
if not root_logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

# .env 読み込み
load_dotenv(override=True)

# 最終フィルタ（DB保存用）の閾値
MIN_PROFIT_YEN = int(os.getenv("MIN_PROFIT_YEN", "700"))
MIN_ROI_PERCENT = float(os.getenv("MIN_ROI_PERCENT", "15"))

# 楽天プレフィルタの閾値（ここを緩める / 0 にすると候補が増える）
PREFILTER_MIN_MAX_POSSIBLE_PROFIT = int(
    os.getenv("PREFILTER_MIN_MAX_POSSIBLE_PROFIT", "0")  # デバッグ用にデフォルト0
)
PREFILTER_MIN_PRICE = int(
    os.getenv("PREFILTER_MIN_PRICE", "0")  # デバッグ用にデフォルト0
)
PREFILTER_MIN_SALES_RANK_DROPS30 = int(
    os.getenv("PREFILTER_MIN_SALES_RANK_DROPS30", "0")  # 0=無効（既存動作維持）
)


def load_query_from_env_or_file() -> str:
    """
    Keepa Product Finder のクエリ文字列を取得する優先順位:

    1. 環境変数 KEEPA_FINDER_QUERY
    2. data/queries/*.txt の先頭1ファイルの中身
    """
    env_query = os.getenv("KEEPA_FINDER_QUERY")
    if env_query:
        return env_query

    queries_dir = Path("data/queries")
    for p in queries_dir.glob("*.txt"):
        return p.read_text(encoding="utf-8")

    raise ValueError("KEEPAクエリが見つかりません（環境変数 or data/queries/*.txt）")


def run_batch_once_noarg() -> Dict[str, Any]:
    """
    data/queries 以下の .txt を全部回して 1本ずつ run_batch_once を実行。
    全体のサマリを返す。
    """
    base = Path("data/queries")
    files = sorted(base.glob("*.txt"))

    if not files:
        logger.warning("data/queries に .txt ファイルがありません")
        return {
            "files": 0,
            "total_asins": 0,
            "total_priced_asins": 0,
            "total_rakuten_candidates": 0,
            "total_final_asins": 0,
            "asin_count": 0,
            "excel_path": None,
            "pricing_quota_suspected": False,
            "fba_quota_suspected": False,
        }

    total_asins = 0
    total_priced_asins = 0
    total_rakuten_candidates = 0
    total_final_asins = 0
    pricing_quota_suspected = False
    fba_quota_suspected = False
    last_excel_path: str | None = None

    for p in files:
        query_str = p.read_text(encoding="utf-8").strip()
        if not query_str:
            logger.warning("%s が空です、スキップします", p)
            continue

        logger.info("[BATCH] Query ファイル: %s", p.name)
        summary = run_batch_once(query_str, logger=logger)

        if not isinstance(summary, dict):
            continue

        total_asins += int(summary.get("total_asins") or 0)
        total_priced_asins += int(summary.get("priced_asins") or 0)
        total_rakuten_candidates += int(summary.get("rakuten_candidates") or 0)
        total_final_asins += int(summary.get("final_candidates") or 0)

        if summary.get("excel_path"):
            last_excel_path = summary["excel_path"]

        if summary.get("pricing_quota_suspected"):
            pricing_quota_suspected = True
        if summary.get("fba_quota_suspected"):
            fba_quota_suspected = True

    return {
        "files": len(files),
        "total_asins": total_asins,
        "total_priced_asins": total_priced_asins,
        "total_rakuten_candidates": total_rakuten_candidates,
        "total_final_asins": total_final_asins,
        "asin_count": total_final_asins,  # 互換用
        "excel_path": last_excel_path,
        "pricing_quota_suspected": pricing_quota_suspected,
        "fba_quota_suspected": fba_quota_suspected,
    }


def run_batch_once(
    query: str,
    logger: logging.Logger | None = None,
) -> Dict[str, Any]:
    """
    GUI なしで 1 回分のバッチを実行する。

    - Keepa Product Finder クエリを受け取り
    - SP-API / Rakuten / FBA手数料を叩き
    - 価格差を計算
    - Excel と DB に保存する

    戻り値（サマリ）例:
        {
            "total_asins": 30,                 # Keepaから取れたASIN数
            "priced_asins": 25,                # Amazon価格が取れたASIN数
            "rakuten_candidates": 10,          # 楽天検索対象
            "final_candidates": 3,             # 条件を満たした最終候補
            "db_saved_asins": 3,               # DB保存件数
            "asin_count": 3,                   # 従来互換（= final_candidates）
            "excel_path": "C:/.../xxx.xlsx",   # 出力先 or None
            "pricing_quota_suspected": False,  # PricingでQuotaExceededっぽい時 True
            "fba_quota_suspected": False,      # FBA手数料でQuotaExceededっぽい時 True
        }
    """
    log = logger or logging.getLogger(__name__)

    start_time = time.time()
    started_at = datetime.utcnow()

    summary: Dict[str, Any] = {
        "total_asins": 0,
        "priced_asins": 0,
        "fba_asins": 0,
        "rakuten_candidates": 0,
        "rakuten_fetched": 0,
        "final_candidates": 0,
        "db_saved_asins": 0,
        "asin_count": 0,
        "excel_path": None,
        "pricing_quota_suspected": False,
        "fba_quota_suspected": False,
        "started_at": started_at.isoformat(),
        "finished_at": None,
        "duration_sec": None,
    }

    log.info("[BATCH] ===== 開始 =====")
    log.info("[BATCH] Query (先頭200文字): %s...", query[:200])

    # 1️⃣ ASIN リスト取得（Keepa Product Finder）
    asins: List[str] = get_asins_from_finder(query)
    n_asins = len(asins)
    summary["total_asins"] = n_asins

    if not asins:
        elapsed = time.time() - start_time
        log.warning("[BATCH] ASIN取得 0件（もしくは失敗） → 処理終了 (%.1f秒)", elapsed)
        summary["finished_at"] = datetime.utcnow().isoformat()
        summary["duration_sec"] = elapsed
        return summary

    elapsed = time.time() - start_time
    log.info("[1/4] ASIN取得完了: %d件 (経過 %.1f秒)", n_asins, elapsed)

    # 2️⃣ Amazon価格取得
    log.info("[BATCH] Amazon価格取得中...")
    amazon_offer_data: Dict[str, Dict[str, Any]] = get_amazon_prices(asins)
    priced_asins = len(amazon_offer_data)
    summary["priced_asins"] = priced_asins

    if priced_asins == 0:
        elapsed = time.time() - start_time
        log.error(
            "[BATCH] Amazon価格が 0件（ASIN=%d件） → Pricing API 側の失敗が疑われます (%.1f秒)",
            n_asins,
            elapsed,
        )
        summary["pricing_quota_suspected"] = True
        summary["finished_at"] = datetime.utcnow().isoformat()
        summary["duration_sec"] = elapsed
        return summary

    if priced_asins < n_asins:
        log.warning(
            "[BATCH] Amazon価格取得 一部のみ成功: %d/%d 件",
            priced_asins,
            n_asins,
        )

    # 2.5️⃣ FBA手数料
    log.info("[BATCH] FBA手数料取得中...")
    amazon_offer_data_with_fee: Dict[str, Dict[str, Any]] = get_amazon_fees_estimate(
        amazon_offer_data
    )
    summary["fba_asins"] = len(amazon_offer_data_with_fee)

    elapsed = time.time() - start_time
    log.info(
        "[2/4] Amazon価格＋手数料取得完了 (ASIN: %d件, 経過 %.1f秒)",
        len(amazon_offer_data_with_fee),
        elapsed,
    )

    # 3️⃣ 楽天検索用プレフィルタ
    log.info(
        "[BATCH] 楽天検索候補の事前絞り込み中... (min_max_possible_profit=%d, min_price=%d, min_drops30=%d)",
        PREFILTER_MIN_MAX_POSSIBLE_PROFIT,
        PREFILTER_MIN_PRICE,
        PREFILTER_MIN_SALES_RANK_DROPS30,
    )
    filtered_for_rakuten, prefilter_excluded = prefilter_for_rakuten(
        amazon_offer_data_with_fee,
        min_max_possible_profit=PREFILTER_MIN_MAX_POSSIBLE_PROFIT,
        min_price=PREFILTER_MIN_PRICE,
        min_sales_rank_drops30=PREFILTER_MIN_SALES_RANK_DROPS30,
    )
    for asin, reason in prefilter_excluded.items():
        log.info("[REJECT] ASIN=%s reason=%s", asin, reason)
    n_filtered = len(filtered_for_rakuten)
    summary["rakuten_candidates"] = n_filtered

    elapsed = time.time() - start_time
    log.info(
        "[3/4] 楽天検索対象: %d件 / 元ASIN: %d件 (経過 %.1f秒)",
        n_filtered,
        len(amazon_offer_data_with_fee),
        elapsed,
    )

    if not filtered_for_rakuten:
        # 利益的に「楽天を見る価値がある候補がなかった」だけなので正常終了扱い
        log.info("[BATCH] 楽天検索対象が 0件 のため終了（候補なし）")
        summary["finished_at"] = datetime.utcnow().isoformat()
        summary["duration_sec"] = elapsed
        return summary

    # 3.5️⃣ 楽天価格取得
    log.info("[BATCH] 楽天価格情報取得中...")
    amazon_offer_data_with_fee_rakuten: Dict[str, Dict[str, Any]] = get_rakuten_info(
        filtered_for_rakuten
    )
    summary["rakuten_fetched"] = len(amazon_offer_data_with_fee_rakuten)

    elapsed = time.time() - start_time
    log.info("[3.5/4] 楽天価格情報取得完了 (経過 %.1f秒)", elapsed)

    reject_counter = Counter(prefilter_excluded.values())
    for asin, data in filtered_for_rakuten.items():
        reason = (data or {}).get("reject_reason")
        if reason:
            log.info("[REJECT] ASIN=%s reason=%s", asin, reason)
            reject_counter[reason] += 1
    for reason, count in reject_counter.most_common():
        log.info("[REJECT_SUMMARY] reason=%s count=%d", reason, count)
    summary["velocity_excluded"] = sum(
        v for k, v in reject_counter.items() if k.startswith("low_sales_velocity")
    )

    # 4️⃣ 価格差計算
    log.info("[BATCH] 価格差計算中...")
    target_result: Dict[str, Dict[str, Any]] = calculate_price_difference(
        amazon_offer_data_with_fee_rakuten
    )
    n_final = len(target_result)
    summary["final_candidates"] = n_final
    summary["asin_count"] = n_final  # 従来互換

    if target_result:
        sample_asin, sample_data = next(iter(target_result.items()))
        log.info("[BATCH DEBUG] SAMPLE asin=%s, data=%s", sample_asin, sample_data)

    # 4.5️⃣ DB 保存用オブジェクト組み立て
    price_results: List[PriceResult] = []

    for asin, data in target_result.items():
        title = data.get("title") or ""
        amazon_url = data.get("amazon_url") or ""
        rakuten_url = data.get("rakuten_url") or data.get("rakuten_url_1")

        amazon_price_raw = data.get("price")

        # 利益（1注文あたり = SKU全体）
        profit_total = data.get("profit_total")

        # 利益率(%)
        rakuten_cost_total = data.get("rakuten_effective_cost_total")
        roi_percent = data.get("roi_percent")

        # フィルタ条件（1注文あたりベース）
        pass_filter = (
            profit_total is not None
            and roi_percent is not None
            and profit_total >= MIN_PROFIT_YEN
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
                rakuten_price=float(rakuten_cost_total)
                if rakuten_cost_total is not None
                else None,
                profit_per_item=float(profit_total)
                if profit_total is not None
                else None,
                roi_percent=float(roi_percent) if roi_percent is not None else None,
                pass_filter=pass_filter,
                checked_at=datetime.utcnow(),
            )
        )

    # 5️⃣ DB へ一括保存
    if price_results:
        asin_count = len(price_results)
        summary["db_saved_asins"] = asin_count
        log.info("[BATCH] DB へ %d 件保存中...", asin_count)
        try:
            save_price_results(price_results)
        except RuntimeError as e:
            # DATABASE_URL 未設定など、設定上の問題によるスキップ（想定内）
            log.warning("[BATCH] DB保存スキップ（DATABASE_URL未設定）: %s", e)
            summary["db_saved_asins"] = 0
        except Exception as e:
            # DB接続失敗・SQL異常など、実行時の異常（想定外）
            log.error("[BATCH] DB保存失敗（接続・SQL異常の可能性）: %s", e)
            summary["db_saved_asins"] = 0

    # Excel 出力（0件でも export_asin_dict_to_excel の仕様に従う）
    excel_path = export_asin_dict_to_excel(target_result)
    summary["excel_path"] = str(excel_path) if excel_path else None

    elapsed = time.time() - start_time
    summary["finished_at"] = datetime.utcnow().isoformat()
    summary["duration_sec"] = elapsed

    log.info(
        "[SUMMARY] 元ASIN: %d件 / 楽天検索対象: %d件 / 価格差候補: %d件",
        summary["total_asins"],
        summary["rakuten_candidates"],
        summary["final_candidates"],
    )
    log.info(
        "[4/4] 価格差候補: %d件, Excel出力: %s / 総処理時間: %.1f秒",
        n_final,
        summary["excel_path"] or "なし",
        elapsed,
    )
    log.info("[BATCH] ===== 終了 =====")

    return summary
