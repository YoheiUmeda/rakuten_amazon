# rakuten_client_jan.py
import os
import re
import time
import requests
import logging
from dotenv import load_dotenv

# .envからAPIキー読込など
load_dotenv(override=True)
logger = logging.getLogger(__name__)


def get_rakuten_info_strict_by_jan(asins: dict) -> dict:
    app_id = os.getenv('RAKUTEN_API_ID')
    sleep_time = float(os.getenv('RAKUTEN_SLEEP_TIME', 1))

    # ✅ ① キャッシュ：結果を再利用してAPIリクエストを抑制
    product_api_cache = {}

    for asin, info in asins.items():
        if info is None:
            logger.info("[SKIP] ASIN=%s → info=None", asin)
            continue

        jan = (info.get('jan') or '').strip()
        if not jan:
            logger.info("[SKIP] ASIN=%s → JANなし", asin)
            continue

        logger.info("[検索開始] ASIN=%s JAN=%s", asin, jan)
        valid_items = []

        # ① IchibaItem/Search でJAN検索
        items = perform_rakuten_api_search(jan, app_id)
        time.sleep(sleep_time)

        if not items:
            logger.info("[NO_HIT] IchibaItem検索→ JAN: %s", jan)
            continue

        for item in items:
            title = item.get('itemName', '')
            price = float(item.get('itemPrice', 0))
            quantity = extract_quantity_from_rakuten_title(title)
            quantity = max(quantity, 1)

            # スキップ条件
            if is_used_product(title, item.get('itemCaption', '')):
                continue

            # ✅ ② ProductSearchで複数キーワードでJANを調査
            keywords = extract_product_code_candidates(title)
            if not keywords:
                keywords = [title]

            found_matching_jan = False
            matched_jan = None

            for kw in keywords:
                kw_norm = kw.strip()
                if not kw_norm:
                    continue

                if kw_norm in product_api_cache:
                    products = product_api_cache[kw_norm]
                else:
                    products = search_rakuten_product_api(kw_norm)
                    product_api_cache[kw_norm] = products
                    time.sleep(sleep_time)

                for prod in products:
                    prod_data = prod.get('Product', {})
                    rakuten_jan = prod_data.get('jan')
                    logger.debug("[JAN照合] kw='%s' → 楽天JAN: %s", kw_norm, rakuten_jan)

                    if rakuten_jan and rakuten_jan == jan:
                        found_matching_jan = True
                        matched_jan = rakuten_jan
                        break

                if found_matching_jan:
                    break

            if not found_matching_jan:
                logger.info("[JAN不一致] 楽天商品からJAN一致せず → skip (ASIN=%s, JAN=%s)", asin, jan)
                continue

            point_rate = float(item.get('pointRate', 0)) / 100
            point = int(price * point_rate)
            effective_per_item = (price - point) / quantity

            valid_items.append({
                'effective_per_item': effective_per_item,
                'rakuten_cost': price,
                'rakuten_point_rate': point_rate,
                'rakuten_point': point,
                'rakuten_postage_flag': int(item.get('postageFlag', 0)),
                'rakuten_effective_cost': price - point,
                'rakuten_quantity': quantity,
                'rakuten_effective_cost_per_item': effective_per_item,
                'rakuten_url': item.get('itemUrl')
            })

        if not valid_items:
            logger.info("[NO_MATCH] JAN一致商品なし: ASIN=%s, JAN=%s", asin, jan)
            continue

        # ③ 上位3件で記録
        valid_items = sorted(valid_items, key=lambda x: x['effective_per_item'])[:3]

        for idx, entry in enumerate(valid_items, start=1):
            for key, value in entry.items():
                info[f"{key}_{idx}"] = value

        # データ補完（1〜3件未満分）
        for idx in range(len(valid_items) + 1, 4):
            for field in ['rakuten_cost', 'rakuten_point_rate', 'rakuten_point',
                          'rakuten_postage_flag', 'rakuten_effective_cost',
                          'rakuten_quantity', 'rakuten_effective_cost_per_item',
                          'rakuten_url']:
                info[f"{field}_{idx}"] = None

    return asins


def perform_rakuten_api_search(keyword: str, app_id: str):
    url = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20170706"
    params = {
        'applicationId': app_id,
        'keyword': keyword,
        'hits': 20,
        'availability': 1,
        'sort': '+itemPrice'
    }
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return [i['Item'] for i in response.json().get('Items', [])]
        else:
            logger.error("[APIエラー] IchibaItemSearch HTTP %s keyword=%s", response.status_code, keyword)
    except Exception as e:
        logger.error("[APIエラー] IchibaItemSearch: %s", e)
    return []


def search_rakuten_product_api(keyword: str):
    app_id = os.getenv('RAKUTEN_API_ID')
    url = "https://app.rakuten.co.jp/services/api/Product/Search/20170426"
    params = {
        'applicationId': app_id,
        'keyword': keyword,
        'hits': 5
    }
    try:
        res = requests.get(url, params=params)
        if res.status_code == 200:
            return res.json().get('Products', [])
        else:
            logger.error("[APIエラー] ProductSearch HTTP %s keyword=%s", res.status_code, keyword)
    except Exception as e:
        logger.error("[APIエラー] ProductSearch: %s", e)
    return []


def extract_product_code_candidates(title):
    # 英字+数字や型番っぽいパターンを抽出
    return list(set(re.findall(r'\b[A-Z0-9\-]{4,}\b', title)))


def is_used_product(title: str, caption: str = "") -> bool:
    used_keywords = ["中古", "used", "リファービッシュ", "再生品", "訳あり", "アウトレット"]
    text = (title + " " + caption).lower()
    return any(kw in text for kw in used_keywords)


EXCLUDE_KEYWORDS = [
    "保証", "延長", "修理", "保護", "フィルム",
    "チケット", "サービス", "まとめ買い", "セット内容", "オプション"
]


def extract_quantity_from_rakuten_title(title: str) -> int:
    import re
    from datetime import datetime

    title = title or ""
    title_lower = title.lower()

    # 1. パック系・箱・BOX等（セット内容やBOX商品は数量1と扱う）
    box_like_words = [
        r'パック\s*入', 'パック入り', r'\bbox\b', 'ボックス', 'booster', 'ブースター',
        'コンプリートセット', '福袋', r'ケース(販売)?', 'オリパ'
    ]
    for w in box_like_words:
        if re.search(w, title_lower):
            logger.debug("[数量特例] '%s' 検出 → 数量=1", w)
            return 1

    # 2. バリエーション（選択式など）は数量1
    if re.search(r'\d+(\s*/\s*\d+){1,2}\s*(本|個|枚|袋|組|色)', title_lower):
        logger.debug("[数量特例] 'n/n構成' バリエーション検出 → 数量=1")
        return 1
    if "選べる" in title_lower or re.search(r'単品\s*/\s*\d+', title_lower):
        logger.debug("[数量特例] '選べる/単品' バリエーション検出 → 数量=1")
        return 1

    # 3. 容量・重量などは構成情報なので除外処理
    excluded_units = ['g', 'mg', 'kg', 'ml', 'l', 'リットル', 'グラム', 'ミリリットル', 'cc', 'カプセル', '粒']
    title_cleaned = title  # ← 元のtitleをコピー

    for ex_unit in excluded_units:
        title_cleaned = re.sub(rf'(\d{{1,4}})\s*{ex_unit}', '', title_cleaned, flags=re.IGNORECASE)

    # 年号除外（2020～現在）← 普通の "数字" 抽出時に誤るため先に除外
    current_year = datetime.now().year
    known_years = [str(y) for y in range(2020, current_year + 1)]

    for year in known_years:
        title_cleaned = title_cleaned.replace(year, '')

    # 4. メディア系コンボ商品を数量1とする
    media_combo_keywords = [
        "blu-ray＋dvd", "blu-ray+dvd", "ブルーレイ＋dvd", "ブルーレイ+dvd",
        "blu-ray&dvd", "ブルーレイ&dvd", "blu-ray/dvd", "ブルーレイ/dvd",
        "コンボパック", "combo pack", "2枚組", "２枚組",
        "cd＋dvd", "限定盤", "特典付き", "2in1", "dual pack",
    ]
    title_lower_clean = title_cleaned.lower()
    for kw in media_combo_keywords:
        if kw in title_lower_clean:
            logger.debug("[数量特例] メディア系 '%s' → 数量=1", kw)
            return 1

    # 5. 通常の数量パターンチェック
    patterns = [
        r'(\d+)\s*個\s*(入|入り|セット)?',
        r'[×ｘxX＊*]\s*(\d+)',
        r'(\d+)\s*(本|袋|箱|パック|セット|枚|組)',
        r'(\d+)\s*個',
    ]

    invalid_suffixes = ['まで', '上限', '限定']
    max_valid_quantity = 200

    for pattern in patterns:
        m = re.search(pattern, title_cleaned)
        if m:
            try:
                quantity = int(m.group(1))

                # 年号の誤認識防止（上で除去済みだけど保険）
                if str(quantity) in known_years:
                    logger.debug("[数量無効] '%s' は年号と一致 → 除外", quantity)
                    continue

                if quantity > max_valid_quantity:
                    logger.debug("[数量無効] '%s' は異常値 → 除外", quantity)
                    continue

                end_index = m.end()
                suffix = title_cleaned[end_index:end_index + 4]
                if any(x in suffix for x in invalid_suffixes):
                    logger.debug("[数量無効] '%s' の後に '%s' → 除外", m.group(), suffix)
                    continue

                return quantity
            except Exception as e:
                logger.exception("[数量抽出エラー] %s", e)
                continue

    return 1
