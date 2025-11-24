# amazon_price.py
from spapi_client import get_best_amazon_price, enrich_results_with_jan
from keepa_client import enrich_results_with_keepa_jan

def get_amazon_prices(asins):
    """
    優先順にAmazonの価格情報を取得し返す
    """
    result = {
        "cart_price": None,
        "lowest_marketplace_price": None,
        "keepa_buybox": None,
        "keepa_new_lowest": None,
        "is_fba": None
    }

    # 1. SP-APIでカート、または価格取得
    amazon_data = get_best_amazon_price(asins)

    # 2. JANコードを付与
    amazon_data_with_jan = enrich_results_with_keepa_jan(amazon_data)

    # # 3. KeepaでBuyBox価格を取得
    # keepa_data = get_keepa_summary(asins)
    # if keepa_data:
    #     result["keepa_buybox"] = keepa_data.get("buybox_new")
    #     result["keepa_new_lowest"] = keepa_data.get("lowest_new")
    #     result["is_fba"] = keepa_data.get("is_fba") if result["is_fba"] is None else result["is_fba"]

    return amazon_data_with_jan
