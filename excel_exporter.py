# excel_exporter.py
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import openpyxl

logger = logging.getLogger(__name__)

# 左側に寄せたい「優先列」
PREFERRED_ORDER: List[str] = [
    "pass_filter",  # フィルタ合格フラグ
    "ASIN",
    "brand",
    "model",
    "title",
    "is_fba",
    "buybox",

    # 価格・利益まわり
    "price",                        # カタログ価格（総額）
    "shipping",                     # 送料
    "amazon_price_per_item",        # 1個あたりカタログ価格
    "amazon_received_per_item",     # 手数料控除後の受取額
    "rakuten_effective_cost_per_item_selected",  # 選択した仕入れ単価
    "profit_per_item",              # 1個あたり利益
    "roi_percent",                  # 利益率（％）
    "price_diff",                   # 利益額（ポイント・手数料控除後）

    # 動き・数量まわり
    "estimated_monthly_sold_30",
    "estimated_monthly_sold",
    "monthly_sold",
    "salesrank_drops30",
    "amazon_quantity",
    "rakuten_quantity_1",

    # 参考：仕入れコスト関連
    "rakuten_effective_cost_total",
    "rakuten_effective_cost_1",
    "rakuten_effective_cost_per_item_1",
    "rakuten_url_1",

    "jan",
]

# 日本語ヘッダマップ（Excelに出すラベルはここが正）
HEADER_MAP_JA: Dict[str, str] = {
    "ASIN": "ASIN",
    "pass_filter": "フィルタ通過",
    "brand": "ブランド",
    "model": "型番",
    "title": "商品タイトル",
    "is_fba": "FBA",
    "buybox": "カート取得",

    "price": "Amazon価格",
    "shipping": "Amazon送料",
    "amazon_price_per_item": "Amazon単価",
    "amazon_received_per_item": "Amazon受取額/個",
    "rakuten_effective_cost_per_item_selected": "楽天単価(採用)",
    "rakuten_effective_cost_total": "楽天仕入合計(参考)",
    "profit_per_item": "利益/個",
    "roi_percent": "利益率(%)",
    "price_diff": "利益額",

    "estimated_monthly_sold_30": "推定月販(30日)",
    "estimated_monthly_sold": "推定月販",
    "monthly_sold": "月販(ベース)",
    "salesrank_drops30": "30日ドロップ数",
    "amazon_quantity": "Amazon在庫数",
    "rakuten_quantity_1": "楽天在庫数(1)",

    "rakuten_effective_cost_1": "楽天仕入額(1)",
    "rakuten_effective_cost_per_item_1": "楽天単価(1)",
    "rakuten_url_1": "楽天URL(1)",

    "jan": "JAN",

    # 手数料系
    "fee": "手数料",
    "fee_raw": "手数料詳細",
    "fba_shipping_fee": "FBA送料",
    "total_fee": "手数料合計",

    # 楽天候補1〜3
    "rakuten_cost_1": "楽天価格(1)",
    "rakuten_point_rate_1": "ポイント率(1)",
    "rakuten_point_1": "ポイント額(1)",
    "rakuten_postage_flag_1": "送料区分(1)",

    "rakuten_cost_2": "楽天価格(2)",
    "rakuten_point_rate_2": "ポイント率(2)",
    "rakuten_point_2": "ポイント額(2)",
    "rakuten_postage_flag_2": "送料区分(2)",
    "rakuten_effective_cost_2": "楽天仕入額(2)",
    "rakuten_quantity_2": "楽天在庫数(2)",
    "rakuten_effective_cost_per_item_2": "楽天単価(2)",
    "rakuten_url_2": "楽天URL(2)",

    "rakuten_cost_3": "楽天価格(3)",
    "rakuten_point_rate_3": "ポイント率(3)",
    "rakuten_point_3": "ポイント額(3)",
    "rakuten_postage_flag_3": "送料区分(3)",
    "rakuten_effective_cost_3": "楽天仕入額(3)",
    "rakuten_quantity_3": "楽天在庫数(3)",
    "rakuten_effective_cost_per_item_3": "楽天単価(3)",
    "rakuten_url_3": "楽天URL(3)",

    "keepa_salesranks": "Keepaランキング履歴",

    # 将来追加分のためのプレースホルダ（必要になったら増やす想定）
    "profit_ok": "粗利下限クリア",
    "roi_ok": "粗利率下限クリア",
}


def export_asin_dict_to_excel(
    asin_data: Dict[str, Dict[str, Any]]
) -> Optional[str]:
    """
    ASINベースの辞書（ネスト形式）をExcelに出力する。

    - 左側に「仕入れ判断用」の重要列を優先的に配置
    - ヘッダは日本語表示
    - .env の EXPORT_ONLY_FILTERED=true で pass_filter==True の行だけ出力
    """
    if not asin_data:
        logger.info("[Excel] 出力対象データが空のためスキップ")
        return None

    # dict -> list[dict]
    rows: List[Dict[str, Any]] = []
    for asin, info in asin_data.items():
        row = {"ASIN": asin}
        if info:
            row.update(info)
        rows.append(row)

    if not rows:
        logger.info("[Excel] rows が空のためスキップ")
        return None

    # --- .env で出力対象を制御：true なら pass_filter==True だけ出力 ---
    export_only_filtered = os.getenv("EXPORT_ONLY_FILTERED", "false").lower() == "true"
    if export_only_filtered:
        filtered_rows = [r for r in rows if r.get("pass_filter")]
        if not filtered_rows:
            logger.warning(
                "[Excel] pass_filter=True の行がないため、全件出力にフォールバックします。"
            )
        else:
            rows = filtered_rows

    # --- すべてのキーを「最初に登場した順」で集約 ---
    all_keys: List[str] = []
    for r in rows:
        for k in r.keys():
            if k not in all_keys:
                all_keys.append(k)

    # --- 優先順＋その他のキーをマージして最終ヘッダを作る ---
    headers: List[str] = []

    # 1) PREFERRED_ORDER にあるキーを左側に
    for key in PREFERRED_ORDER:
        if key in all_keys and key not in headers:
            headers.append(key)

    # 2) 残りのキー（fee_raw や 楽天2・3候補など）は右側にまとめて並べる
    for key in all_keys:
        if key not in headers:
            headers.append(key)

    # --- ファイル名・保存先 ---
    now_str = datetime.now().strftime("%Y%m%d%H%M%S")
    filename = f"{now_str}_output.xlsx"
    output_dir = os.getenv("OUTPUT_DIR_PATH") or "output"
    os.makedirs(output_dir, exist_ok=True)
    full_path = os.path.join(output_dir, filename)

    wb = openpyxl.Workbook()
    ws = wb.active

    # 1行目：日本語ヘッダを出力
    header_labels = [HEADER_MAP_JA.get(h, h) for h in headers]
    ws.append(header_labels)

    # 2行目以降：データ行
    for row in rows:
        safe_row: List[Any] = []
        for h in headers:
            val = row.get(h)
            # list/dict は文字列化して潰す
            if isinstance(val, (list, dict)):
                safe_row.append(str(val))
            else:
                safe_row.append(val)
        ws.append(safe_row)

    wb.save(full_path)
    logger.info("✅ Excelに出力しました: %s (行数: %d)", full_path, len(rows))
    return full_path
