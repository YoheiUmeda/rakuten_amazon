import requests
import os

def get_latest_valid_price(csv_data):
    if not csv_data or len(csv_data) < 2:
        return None
    for i in range(len(csv_data) - 1, 0, -2):
        price = csv_data[i]
        if price is not None and price != -1:
            return price
    return None

def get_keepa_summary(asins):
    api_key = os.getenv('KEEPA_API_KEY')
    url = 'https://api.keepa.com/product'
    headers = {'Accept-Encoding': 'gzip'}
    results = {}
    # 最大100ASINまとめてリクエスト可
    for i in range(0, len(asins), 100):
        params = {'key': api_key, 'domain': 6, 'asin': ','.join(asins[i:i+100]), 'buybox': 1, 'stats':1, 'history':1}
        r = requests.get(url, params=params, headers=headers)
        products = r.json().get('products', [])
        for p in products:
            asin, fba = p['asin'], p.get('fbaFees') is not None
            # BuyBox新品：index=10、マーケットプレイス新品=1
            bb = get_latest_valid_price(p['csv'][10]) if len(p['csv']) > 10 else None
            np = get_latest_valid_price(p['csv'][1]) if len(p['csv']) > 1 else None
            price = bb if bb is not None else np
            results[asin] = {"amz_price": price, "is_fba": fba}
    return results
