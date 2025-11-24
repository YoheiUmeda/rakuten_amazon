# 日本語ヘッダマップ（必要に応じて増やす）
JP_HEADER_MAP = {
    "ASIN": "ASIN",
    "price": "Amazon販売価格",
    "shipping": "Amazon送料",
    "is_fba": "FBA出品",
    "buybox": "カート取得",
    "seller": "出品者ID",
    "title": "商品タイトル",
    "amazon_quantity": "Amazon在庫数",
    "amazon_price_per_item": "Amazon単価(セット割戻し)",
    "jan": "JANコード",
    "brand": "ブランド",
    "model": "型番",
    "salesrank_drops30": "30日ランク降下回数",
    "monthly_sold": "月間販売数(Keepa)",
    "estimated_monthly_sold": "推定月販(総合)",
    "estimated_monthly_sold_30": "推定月販(30日)",
    "estimated_monthly_sold_60": "推定月販(60日)",
    "estimated_monthly_sold_90": "推定月販(90日)",
    "keepa_salesranks": "Keepaランク履歴",

    "fee": "FBA手数料合計",
    "fee_raw": "FBA手数料詳細(raw)",
    "fba_shipping_fee": "FBA配送料",
    "total_fee": "Amazon手数料総額",

    "effective_per_item_1": "仕入総額1(ポイント前)",
    "rakuten_cost_1": "楽天価格1",
    "rakuten_point_rate_1": "ポイント率1",
    "rakuten_point_1": "ポイント1",
    "rakuten_postage_flag_1": "送料別フラグ1",
    "rakuten_effective_cost_1": "楽天実質仕入額1",
    "rakuten_quantity_1": "楽天在庫数1",
    "rakuten_effective_cost_per_item_1": "楽天実質単価1",
    "rakuten_url_1": "楽天URL1",

    "effective_per_item_2": "仕入総額2(ポイント前)",
    "rakuten_cost_2": "楽天価格2",
    "rakuten_point_rate_2": "ポイント率2",
    "rakuten_point_2": "ポイント2",
    "rakuten_postage_flag_2": "送料別フラグ2",
    "rakuten_effective_cost_2": "楽天実質仕入額2",
    "rakuten_quantity_2": "楽天在庫数2",
    "rakuten_effective_cost_per_item_2": "楽天実質単価2",
    "rakuten_url_2": "楽天URL2",

    "effective_per_item_3": "仕入総額3(ポイント前)",
    "rakuten_cost_3": "楽天価格3",
    "rakuten_point_rate_3": "ポイント率3",
    "rakuten_point_3": "ポイント3",
    "rakuten_postage_flag_3": "送料別フラグ3",
    "rakuten_effective_cost_3": "楽天実質仕入額3",
    "rakuten_quantity_3": "楽天在庫数3",
    "rakuten_effective_cost_per_item_3": "楽天実質単価3",
    "rakuten_url_3": "楽天URL3",

    "amazon_received_per_item": "Amazon受取額(1個あたり)",
    "rakuten_effective_cost_total": "楽天実質仕入総額(採用候補)",
    "rakuten_effective_cost_per_item_selected": "楽天実質仕入単価(採用)",
    "price_diff": "価格差(Amazon-楽天)",
    "price_diff_after_point": "ポイント考慮後価格差",
    "profit_per_item": "粗利(1個あたり)",
    "profit_rate": "粗利倍率",     # = 粗利 / 仕入
    # ↓ここから新しく追加する列
    "roi_percent": "粗利率(%)",
    "profit_ok": "粗利下限クリア",
    "roi_ok": "粗利率下限クリア",
    "pass_filter": "仕入候補フラグ",
}

def export_asin_dict_to_excel(asin_data: dict):
    """
    ASINベースの辞書（ネスト形式）をExcel用の一覧リストに変換して出力する。
    - 左側に「仕入れ判断用」の重要列を優先的に配置
    - ヘッダは日本語表示
    - .env の EXPORT_ONLY_FILTERED=true で pass_filter==True の行だけ出力
    """
    import os
    import openpyxl
    from datetime import datetime

    if not asin_data:
        return None

    # dict -> list[dict]
    rows = []
    for asin, info in asin_data.items():
        row = {"ASIN": asin}
        row.update(info)
        rows.append(row)

    if not rows:
        return

    # --- .env で出力対象を制御：true なら pass_filter==True だけ出力 ---
    export_only_filtered = os.getenv("EXPORT_ONLY_FILTERED", "false").lower() == "true"
    if export_only_filtered:
        filtered_rows = [r for r in rows if r.get("pass_filter")]
        
        if not filtered_rows:
            print("⚠ pass_filter=True の行がないため、全件出力にフォールバックします。")
            # rows はそのまま全件を使う
        else:
            rows = filtered_rows

    # --- すべてのキーを「最初に登場した順」で集約 ---
    all_keys = []
    for r in rows:
        for k in r.keys():
            if k not in all_keys:
                all_keys.append(k)

    # --- 左側に寄せたい「優先列」（英語キー） ---
    # いまのデータ構造を前提に、仕入れ判断でよく見るものを並べている
    preferred_order = [
        "pass_filter",                  # フィルタ合格フラグ
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
        "price_diff_after_point",       # ポイント込み差額
        "price_diff",                   # 純粋な価格差

        # 動き・数量まわり
        "estimated_monthly_sold_30",
        "estimated_monthly_sold",
        "monthly_sold",
        "salesrank_drops30",
        "amazon_quantity",
        "rakuten_quantity_1",

        # 参考：仕入れコスト関連（合計・楽天1）
        "rakuten_effective_cost_total",
        "rakuten_effective_cost_1",
        "rakuten_effective_cost_per_item_1",
        "rakuten_url_1",

        # ここまでが「左側で主に見る列」のイメージ
        "jan",
    ]

    # --- 優先順＋その他のキーをマージして最終ヘッダを作る ---
    headers = []

    # 1) preferred_order にあるキーを左側に
    for key in preferred_order:
        if key in all_keys and key not in headers:
            headers.append(key)

    # 2) 残りのキー（fee_raw や 楽天2・3候補など）は右側にまとめて並べる
    for key in all_keys:
        if key not in headers:
            headers.append(key)

    # --- 日本語表示用ヘッダマップ ---
    header_map_ja = {
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
        "price_diff_after_point": "差額(ポイント込)",
        "price_diff": "差額(ポイント除外)",

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

        # 既に持っているであろうその他の列も、必要に応じて追加していく想定
        "fee": "手数料",
        "fee_raw": "手数料詳細",
        "fba_shipping_fee": "FBA送料",
        "total_fee": "手数料合計",

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
    }

    # --- ファイル名・保存先 ---
    now_str = datetime.now().strftime('%Y%m%d%H%M%S')
    filename = f"{now_str}_output.xlsx"
    output_dir = os.getenv('OUTPUT_DIR_PATH') or '.'
    full_path = os.path.join(output_dir, filename)

    wb = openpyxl.Workbook()
    ws = wb.active

    # 1行目：日本語ヘッダを出力
    header_labels = [header_map_ja.get(h, h) for h in headers]
    ws.append(header_labels)

    # 2行目以降：データ行（キーは英語ヘッダを使う）
    for row in rows:
        safe_row = []
        for h in headers:
            val = row.get(h)
            if isinstance(val, (list, dict)):
                safe_row.append(str(val))
            else:
                safe_row.append(val)
        ws.append(safe_row)

    wb.save(full_path)
    print(f"✅ Excelに出力しました: {full_path}")
    return full_path
