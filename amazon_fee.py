from spapi_client import get_fba_fee
from dotenv import load_dotenv
import csv
import os

load_dotenv(override=True)

def get_amazon_fees_estimate(asin_price_map):
    results = get_fba_fee(asin_price_map)
    result_with_fees = annotate_fees_to_asin_price_map(asin_price_map, results)
    return result_with_fees

# ✅ 1. CSV読み込み（Amazon公式手数料表をパース）
def load_fba_fee_table(path=None):
    """
    Amazon FBA手数料CSVをファイルから読み込む。
    path が指定されない場合は .env の変数またはデフォルト（相対）を使う。
    """
    # デフォルトの相対パス or .env の指定
    rel_path = path or os.getenv('FBA_FEE_TABLE_PATH', 'data/fba_fee_table.csv')

    # ✅ 絶対パス化：このスクリプトファイル基準に解決
    base_dir = os.path.dirname(os.path.abspath(__file__))
    abs_path = os.path.join(base_dir, rel_path)

    if not os.path.exists(abs_path):
        raise FileNotFoundError(
            f"[ERROR] FBA手数料ファイルが見つかりません: {abs_path}\n"
            f"現在のカレントディレクトリ: {os.getcwd()}"
        )
    fee_table = []

    with open(abs_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            fee_table.append({
                "サイズ区分": row["サイズ区分"],
                "重量上限": int(row["重量グラム上限"]),
                "手数料": int(row["手数料"])
            })
    return fee_table

# ✅ 2. 梱包サイズ（cm）と重量（g）からAmazonサイズ区分を判定
def get_size_category_by_dimensions(weight_g, dimensions_cm):
    if not dimensions_cm or len(dimensions_cm) != 3 or weight_g is None:
        return "標準"

    length, width, height = sorted(dimensions_cm, reverse=True)
    weight_kg = weight_g / 1000

    if length <= 60 and width <= 35 and height <= 3 and weight_kg <= 0.25:
        return "小型"
    elif length <= 60 and width <= 45 and height <= 35 and weight_kg <= 1.0:
        return "標準"
    elif length <= 80 and width <= 60 and height <= 50 and weight_kg <= 9:
        return "大型1"
    elif length <= 140 and width <= 60 and height <= 60 and weight_kg <= 15:
        return "大型2"
    else:
        return "超大型"

# ✅ 3. サイズ区分と重さに応じて csv から配送手数料を取得
def estimate_fba_shipping_fee_by_dimensions(weight_g, dimensions_cm, fee_table):
    category = get_size_category_by_dimensions(weight_g, dimensions_cm)
    for fee_entry in fee_table:
        if fee_entry['サイズ区分'] == category and weight_g <= fee_entry['重量上限']:
            return fee_entry['手数料']
    return 485  # fallback


# ✅ 4. メイン処理：拡張版 annotate_fees_to_asin_price_map
def annotate_fees_to_asin_price_map(asin_price_map, results, size_db=None, fee_table_path=None):
    fee_table_path = fee_table_path or os.getenv("FBA_FEE_TABLE_PATH")
    fee_table = load_fba_fee_table(fee_table_path)
    enriched = {asin: data.copy() for asin, data in asin_price_map.items()}

    def apply_shipment_fee(asin, data):
        if size_db and asin in size_db:
            dims = size_db[asin].get("dimensions_cm")
            weight = size_db[asin].get("weight_g")
            fba_fee = estimate_fba_shipping_fee_by_dimensions(weight, dims, fee_table)
        else:
            fba_fee = 485  # fallback
        return fba_fee

    if isinstance(results, list):
        for item in results:
            if not isinstance(item, dict):
                print(f"[WARNING] unexpected item skipped: {item}")
                continue

            asin = item.get('FeesEstimateIdentifier', {}).get('IdValue')
            status = item.get('Status')

            if asin not in enriched:
                continue

            if status == "Success":
                fee = item.get('FeesEstimate', {}) \
                    .get('TotalFeesEstimate', {}) \
                    .get('Amount')
                enriched[asin]['fee'] = fee
                enriched[asin]['fee_raw'] = item.get('FeesEstimate', {}).get('FeeDetailList', [])

                shipping_fee = apply_shipment_fee(asin, enriched[asin])
                enriched[asin]['fba_shipping_fee'] = shipping_fee
                enriched[asin]['total_fee'] = (fee or 0) + shipping_fee
            else:
                enriched[asin]['fee'] = None
                enriched[asin]['fba_shipping_fee'] = None
                enriched[asin]['total_fee'] = None

    elif isinstance(results, dict):
        for asin, item in results.items():
            if asin not in enriched:
                continue

            fee = item.get("fee")
            enriched[asin]["fee"] = fee
            enriched[asin]["fee_raw"] = item.get("fee_raw", [])

            shipping_fee = apply_shipment_fee(asin, enriched[asin])
            enriched[asin]['fba_shipping_fee'] = shipping_fee
            enriched[asin]['total_fee'] = (fee or 0) + shipping_fee

    else:
        print("[ERROR] annotate_fees_to_asin_price_map: results は list または dict である必要があります")

    return enriched