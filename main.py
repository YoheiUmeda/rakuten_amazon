# main.py
from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime

import tkinter as tk
from tkinter import scrolledtext, messagebox

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from prefilter import prefilter_for_rakuten
from keepa_client import get_asins_from_finder
from amazon_fee import get_amazon_fees_estimate
from amazon_price import get_amazon_prices
from rakuten_client import get_rakuten_info
from price_calculation import calculate_price_difference
from excel_exporter import export_asin_dict_to_excel
from app.schemas import PriceResult
from app.repository import save_price_results
from app.api import prices

# .env 読み込み（FastAPI側/バッチ側どちらで使ってもいいように先頭で呼ぶ）
load_dotenv(override=True)

logger = logging.getLogger(__name__)

# =========================
# FastAPI アプリ設定
# =========================

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(prices.router, prefix="/api")

LOG_PATH: str | None = None

# 利益フィルタのしきい値（1注文あたり）
MIN_PROFIT_YEN = int(os.getenv("MIN_PROFIT_YEN", "700"))
MIN_ROI_PERCENT = float(os.getenv("MIN_ROI_PERCENT", "15"))


def update_status(status_label: tk.Label, root: tk.Tk, text: str) -> None:
    """ステータスラベル更新を1箇所に集約"""
    status_label["text"] = text
    root.update_idletasks()


def worker(query: str, root: tk.Tk, status_label: tk.Label, btn_run: tk.Button) -> None:
    """
    Keepa Product Finder → SP-API → 楽天 → 価格差計算 → Excel & DB 保存
    を1スレッドでまとめて実行するワーカー。
    """
    start_time = time.time()
    log = logging.getLogger(__name__)

    try:
        # 1️⃣ ASIN取得
        update_status(status_label, root, "ASINリスト取得中...")
        asins = get_asins_from_finder(query)
        n_asins = len(asins)

        if not asins:
            msg = "ASIN取得0件（もしくは失敗）"
            log.warning(msg)
            update_status(status_label, root, msg)
            return

        elapsed = time.time() - start_time
        msg = f"[1/4] ASIN取得完了: {n_asins}件 (経過 {elapsed:.1f}秒)"
        log.info(msg)
        update_status(status_label, root, msg)

        # 2️⃣ Amazon価格＋手数料
        update_status(status_label, root, "Amazon価格取得中...")
        amazon_offer_data = get_amazon_prices(asins)

        update_status(status_label, root, "FBA手数料取得中...")
        amazon_offer_data_with_fee = get_amazon_fees_estimate(amazon_offer_data)

        elapsed = time.time() - start_time
        msg = (
            f"[2/4] Amazon価格＋手数料取得完了 "
            f"(ASIN: {len(amazon_offer_data_with_fee)}件, 経過 {elapsed:.1f}秒)"
        )
        log.info(msg)
        update_status(status_label, root, msg)

        # 3️⃣ 楽天対象のプレフィルタ
        update_status(status_label, root, "楽天検索候補の事前絞り込み中...")
        filtered_for_rakuten = prefilter_for_rakuten(
            amazon_offer_data_with_fee,
            min_max_possible_profit=1500,
            min_price=3000,
        )
        n_filtered = len(filtered_for_rakuten)
        elapsed = time.time() - start_time

        msg = (
            f"[3/4] 楽天検索対象: {n_filtered}件 / "
            f"元ASIN: {len(amazon_offer_data_with_fee)}件 (経過 {elapsed:.1f}秒)"
        )
        log.info(
            "[3/4] 楽天検索対象: %d件 / 元ASIN: %d件 (経過 %.1f秒)",
            n_filtered,
            len(amazon_offer_data_with_fee),
            elapsed,
        )
        update_status(status_label, root, msg)

        if not filtered_for_rakuten:
            msg = "楽天検索対象が0件のため終了"
            log.info(msg)
            update_status(status_label, root, msg)
            return

        # 3.5️⃣ 楽天価格取得
        update_status(status_label, root, "楽天価格情報取得中...")
        amazon_offer_data_with_fee_rakuten = get_rakuten_info(filtered_for_rakuten)

        elapsed = time.time() - start_time
        msg = f"[3.5/4] 楽天価格情報取得完了 (経過 {elapsed:.1f}秒)"
        log.info(msg)
        update_status(status_label, root, msg)

        # 4️⃣ 価格差計算
        update_status(status_label, root, "価格差計算中...")
        target_result = calculate_price_difference(amazon_offer_data_with_fee_rakuten)
        n_final = len(target_result)

        # デバッグ用に先頭1件だけログ出力
        if target_result:
            sample_asin, sample_data = next(iter(target_result.items()))
            log.info("[DEBUG] SAMPLE asin=%s, data=%s", sample_asin, sample_data)

        # 4-1️⃣ DB保存用 PriceResult リスト組み立て
        price_results: list[PriceResult] = []

        for asin, data in target_result.items():
            title = data.get("title") or ""

            # Amazon URL は repository 側で ASIN から補完するのでここでは空でもOK
            amazon_url = data.get("amazon_url") or ""
            rakuten_url = data.get("rakuten_url") or data.get("rakuten_url_1")

            # --- 価格情報（1注文＝1セット単位） ---
            amazon_price_raw = data.get("price")  # SP-API の ListingPrice
            rakuten_price_total = data.get("rakuten_effective_cost_total")

            # --- 利益・ROI（1注文あたり） ---
            profit_total = data.get("profit_total")
            if profit_total is None:
                # 後方互換用：price_calculation が price_diff* を持っているケース
                profit_total = data.get("price_diff_after_point") or data.get("price_diff")

            roi_ratio = data.get("roi_total")
            if roi_ratio is None and profit_total is not None and rakuten_price_total:
                try:
                    base = float(rakuten_price_total)
                    if base > 0:
                        roi_ratio = float(profit_total) / base
                except Exception:
                    roi_ratio = None

            roi_percent = roi_ratio * 100.0 if roi_ratio is not None else None

            # --- フィルタ判定（1注文あたりベース） ---
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
                    rakuten_price=float(rakuten_price_total)
                    if rakuten_price_total is not None
                    else None,
                    # DB上は「1注文あたり利益」として扱う
                    profit_per_item=float(profit_total)
                    if profit_total is not None
                    else None,
                    roi_percent=float(roi_percent)
                    if roi_percent is not None
                    else None,
                    # diff も 1注文あたり利益として保存
                    diff=float(profit_total) if profit_total is not None else None,
                    pass_filter=pass_filter,
                    checked_at=datetime.utcnow(),
                )
            )

        # 4-2️⃣ DB に一括保存
        if price_results:
            save_price_results(price_results)

        # 4-3️⃣ Excel 出力（既存機能）
        excel_path = export_asin_dict_to_excel(target_result)
        candidate_count = len(target_result)

        log.info(
            "[SUMMARY] 元ASIN: %d件 / 楽天検索対象: %d件 / 価格差候補: %d件",
            len(amazon_offer_data),
            len(filtered_for_rakuten),
            candidate_count,
        )

        elapsed = time.time() - start_time
        excel_display = excel_path if excel_path else "（Excel出力なし）"

        msg = (
            f"[4/4] 価格差候補: {n_final}件, Excel出力完了 ({excel_display}) "
            f"/ 総処理時間: {elapsed:.1f}秒"
        )
        log.info(msg)
        update_status(status_label, root, msg)

        log_name = os.path.basename(LOG_PATH) if LOG_PATH else "（logsフォルダを参照）"

        messagebox.showinfo(
            "完了",
            f"Excelに保存しました:\n{excel_display}\n"
            f"候補件数: {n_final}件\n"
            f"総処理時間: {elapsed:.1f}秒\n"
            f"ログファイル: {log_name}",
        )

    except Exception as e:
        log.exception("処理中にエラー発生: %s", e)
        update_status(status_label, root, f"エラー: {e}")
        messagebox.showerror("エラー", str(e))
    finally:
        btn_run.config(state="normal")


def run_search(
    entry_query: scrolledtext.ScrolledText,
    root: tk.Tk,
    status_label: tk.Label,
    btn_run: tk.Button,
) -> None:
    """
    ボタン押下時に呼ばれる関数。
    ここでは入力取得＋スレッド起動だけやる。
    """
    query = entry_query.get("1.0", tk.END).strip()
    if not query:
        status_label["text"] = "クエリを入力してください"
        return

    # 二重起動防止
    btn_run.config(state="disabled")
    update_status(status_label, root, "処理を開始しました...")

    # 重い処理を別スレッドで実行
    t = threading.Thread(
        target=worker,
        args=(query, root, status_label, btn_run),
        daemon=True,
    )
    t.start()


if __name__ == "__main__":
    # GUI 起動時だけログ設定や Tk を立ち上げる
    base_dir = os.path.dirname(os.path.abspath(__file__))
    log_dir = os.path.join(base_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)

    ts = time.strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(log_dir, f"run_{ts}.log")

    # ※ root ロガーをここでだけ初期化（FastAPI/uvicorn利用時は uvicorn 側に任せる）
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )

    LOG_PATH = log_path

    logger = logging.getLogger(__name__)
    logger.info("ログ開始: %s", log_path)

    root = tk.Tk()
    root.title("Product Finder価格差調査")
    root.geometry("600x500")

    tk.Label(root, text="Product Finderクエリ(json or URL)").pack()

    entry_query = scrolledtext.ScrolledText(root, height=8, width=70)
    entry_query.pack()

    status_label = tk.Label(root, text="")
    status_label.pack(pady=(5, 5))

    btn_run = tk.Button(
        root,
        text="実行",
        command=lambda: run_search(entry_query, root, status_label, btn_run),
    )
    btn_run.pack(pady=10)

    root.mainloop()
