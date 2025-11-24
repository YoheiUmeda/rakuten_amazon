# rakuten_client.py
import os
import re
import urllib.parse
import requests
import time
import logging
from dotenv import load_dotenv
from typing import Dict

# .envからAPIキー読込など
load_dotenv(override=True)
logger = logging.getLogger(__name__)

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

    # 年号除外（2020～現在）
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


def is_used_product(title: str, caption: str = "") -> bool:
    used_keywords = ["中古", "used", "リファービッシュ", "再生品", "訳あり", "アウトレット"]
    text = (title + " " + caption).lower()
    return any(kw in text for kw in used_keywords)


def escape_rakuten_keyword(
    keyword: str,
    fallback: str,
    byte_limit: int = 800,
    suggest_words: set = None,
    trending_words: set = None
) -> str:
    if not fallback or len(fallback.strip()) < 4:
        raise ValueError("fallback(JAN/ASIN等)が未設定、または短すぎます")

    if not keyword or not keyword.strip():
        logger.debug("[楽天 keyword] 空入力 → fallback を使用")
        return fallback

    original = keyword
    keyword = re.sub(
        r'[【】「」『』〈〉《》（）()｛｝{}\[\]<>・★☆※〜→←⇒％%!?@#$^&*_+=|\\/,:・。，、。｡･：・‥’‘“”\'"]+',
        ' ',
        keyword
    )
    keyword = re.sub(r'[\u2000-\u206F\u3000-\u303F]', ' ', keyword)
    keyword = re.sub(r'\s+', ' ', keyword).strip()

    stopwords = set([
        '付き', '対応', '可能', '製', '採用', '便利', '簡単', '最適', '収納', '搭載',
        '商品', 'セット', 'サイズ', '色', 'ブラック', 'ホワイト', '純正', '大容量',
        '仕様', '国内正規品', '国内正規', '正規品'
    ])

    tokens = [t for t in keyword.split() if len(t) > 1 and t not in stopwords]
    if not tokens:
        logger.debug("[楽天 keyword] トークン除去後に何も残らない → fallback")
        return fallback

    scored_tokens = []
    for token in tokens:
        score = 0
        if suggest_words and token in suggest_words:
            score += 2
        if trending_words and token in trending_words:
            score += 1
        scored_tokens.append((token, score))

    sorted_tokens = sorted(scored_tokens, key=lambda x: (-x[1], tokens.index(x[0])))

    final_tokens, total_bytes = [], 0
    for token, _ in sorted_tokens:
        token_bytes = len(token.encode('utf-8')) + 1
        if total_bytes + token_bytes > byte_limit:
            break
        final_tokens.append(token)
        total_bytes += token_bytes

    keyword = ' '.join(final_tokens).strip()
    encoded = urllib.parse.quote(keyword, safe='')

    if not keyword or len(encoded.encode('utf-8')) > byte_limit:
        logger.warning("[楽天 keyword] エンコード後にバイト長オーバー → fallback: %s", fallback)
        return fallback

    # if len(keyword) < 4 or re.fullmatch(r'[a-zA-Z0-9\- ]+', keyword):
    #     logger.debug("[楽天 keyword] 内容が希薄/単純文字列 → fallback: %s", fallback)
    #     return fallback

    if len(keyword) < 4:
        return fallback  # 長さチェックのみ残す

    logger.info("[楽天キーワード生成] 原文: %s → 使用: %s", original, keyword)
    return keyword


def extract_core_tokens(title: str) -> str:
    # 主要な型番・カテゴリ語だけ抽出。必要があれば拡張可能
    model = ""
    m = re.search(r'\b([A-Z0-9\-]{4,})\b', title)
    if m:
        model = m.group(1)

    keywords = []
    major_words = ['防音', '吸音', 'ブース', 'マイク', 'ケース', 'ヘッドホン', 'ストラップ', 'カバー', '椅子', 'ピアノ', 'パーテーション']
    for w in major_words:
        if w in title:
            keywords.append(w)
    if model:
        keywords.append(model)
    return ' '.join(keywords) if keywords else title


def perform_rakuten_api_search(keyword: str, app_id: str):
    url = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20170706"
    params = {
        'applicationId': app_id,
        'keyword': keyword,
        'hits': 20,
        'sort': '+itemPrice',
        'field': 0,
        'availability': 1
    }
    logger.debug(f"[RakutenAPI] keyword={keyword} params={params}")

    try:
        r = requests.get(url, params=params)
        if r.status_code == 429 or ('error' in r.text and 'too_many_requests' in r.text):
            logger.warning(f"[RakutenAPI] レート制限 status={r.status_code} keyword={keyword}")
            time.sleep(10)
            return perform_rakuten_api_search(keyword, app_id)

        if r.status_code != 200:
            logger.error(f"[RakutenAPI] HTTP {r.status_code} keyword={keyword}")
            return []

        js = r.json()
        if "error" in js:
            logger.error(f"[RakutenAPI] APIエラー error={js['error']} keyword={keyword}")
            if js["error"] == "too_many_requests":
                time.sleep(10)
                return perform_rakuten_api_search(keyword, app_id)
            return []

        items = js.get('Items', [])
        logger.info(f"[RakutenAPI] keyword={keyword} hit={len(items)}件")
        return [itemBlock['Item'] for itemBlock in items]

    except Exception as e:
        logger.error(f"[RakutenAPI] 例外 keyword={keyword} → {e}")
        return []


def perform_rakuten_api_search_from_itemcode(itemcode: str, app_id: str):
    """API呼出し（エラーハンドリング付・結果返却）"""
    url = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20170706"
    params = {
        'applicationId': app_id,
        'itemCode': itemcode,
        'hits': 20,
        'sort': '+itemPrice',
        'field': 0,
        'availability': 0
    }
    try:
        r = requests.get(url, params=params)
        if r.status_code == 429 or ('error' in r.text and 'too_many_requests' in r.text):
            logger.warning("[楽天API] レート制限, スリープしてリトライ itemcode=%s", itemcode)
            time.sleep(10)
            return perform_rakuten_api_search_from_itemcode(itemcode, app_id)
        if r.status_code != 200:
            logger.error("[楽天APIエラー] status=%s itemcode=%s", r.status_code, itemcode)
            return []
        js = r.json()
        if "error" in js:
            logger.error("[楽天APIエラー] error=%s itemcode=%s", js["error"], itemcode)
            if js["error"] == "too_many_requests":
                time.sleep(10)
                return perform_rakuten_api_search_from_itemcode(itemcode, app_id)
            return []
        items = js.get('Items', [])
        return [itemBlock['Item'] for itemBlock in items]
    except Exception as e:
        logger.error("[楽天APIエラー/例外] itemcode=%s → %s", itemcode, e)
        return []


def get_rakuten_info(asins: dict) -> dict:
    app_id = os.getenv('RAKUTEN_API_ID')
    sleep_time = float(os.getenv('RAKUTEN_SLEEP_TIME', 1))

    total = len(asins)
    for idx, (asin, info) in enumerate(asins.items(), start=1):
        logger.info(f"[楽天 {idx}/{total}] ASIN={asin}")

        if info is None:
            logger.info(f"[楽天SKIP] ASIN={asin} → infoがNone")
            continue

        title = (info.get('title') or '').strip()
        jan = (info.get('jan') or '').strip()
        brand = (info.get('brand') or '').strip()
        model = (info.get('model') or '').strip()
        fallback = jan if len(jan) >= 4 else asin

        item_infos = []
        items = []

        # ❶ JAN検索
        if len(jan) >= 4:
            logger.info(f"[Rakuten] ASIN={asin} JAN検索: {jan}")
            items = perform_rakuten_api_search(jan, app_id)
            time.sleep(sleep_time)

        # ❷ 商品名で再検索
        if not items:
            try:
                keyword = escape_rakuten_keyword(title, fallback)
                logger.info(f"[Rakuten] ASIN={asin} タイトル検索: {keyword}")
                items = perform_rakuten_api_search(keyword, app_id)
                time.sleep(sleep_time)
            except ValueError as ve:
                logger.warning(f"[Rakuten] ASIN={asin} タイトル検索スキップ fallback不正: {ve}")
                items = []

        # ③ 商品番号候補抽出→IchibaItemSearch
        if not items:
            logger.info(f"[Rakuten] NO_HIT ASIN={asin}, fallback={fallback}")
            codes = extract_product_code_candidates(title)
            if codes:
                keyword = " ".join(codes)
                logger.info(f"[楽天Product候補結合キーワード検索] keyword: {keyword}")
                items = perform_rakuten_api_search(keyword, app_id)

                # janを含むitemNameまたはitemCaptionの商品を除外したitemsにする
                if jan:
                    items = [
                        item for item in items
                        if jan not in (item.get('itemName', '') + item.get('itemCaption', ''))
                    ]

        # ② JANでNO_HIT→メーカー名＋型番で検索
        if not items:
            if brand and model:
                keyword_brand_model = f"{brand} {model}".strip()
                if len(keyword_brand_model) >= 4:
                    try:
                        logger.info(f"[楽天再検索] メーカー＋型番で検索: {keyword_brand_model}")
                        items = perform_rakuten_api_search(keyword_brand_model, app_id)
                        time.sleep(sleep_time)
                    except Exception as ve:
                        logger.warning(f"[楽天SKIP] ASIN={asin} → メーカー＋型番検索時エラー: {ve}")
                        items = []

        # ❸ 型番等 短縮キーワード最終検索
        if not items:
            short_kw = extract_core_tokens(title)
            try:
                keyword_retry = escape_rakuten_keyword(short_kw, fallback)
                logger.info(f"[楽天最終検索] 短縮: {keyword_retry}")
                items = perform_rakuten_api_search(keyword_retry, app_id)
                time.sleep(sleep_time)
            except ValueError as ve:
                logger.warning(f"[楽天SKIP] ASIN={asin} → fallback不正(2): {ve}")
                items = []

        # 結果処理
        if not items:
            logger.info(f"[楽天NO_HIT] ASIN={asin}, fallback={fallback}")

        for item in items:
            title = item.get('itemName') or ""
            caption = item.get('itemCaption', "")

            # logger.debug("[DEBUG] brand: %s", brand)
            # logger.debug("[DEBUG] model: %s", model)
            # logger.debug("[DEBUG] title: %s", title)
            # logger.debug("[DEBUG] caption: %s", caption)

            if is_used_product(title, caption):
                continue
            if any(kw in title for kw in EXCLUDE_KEYWORDS):
                continue

            price = float(item.get('itemPrice', 0))
            point_rate = float(item.get('pointRate', 0)) / 100
            point = int(price * point_rate)
            quantity = extract_quantity_from_rakuten_title(title)
            quantity = max(quantity, 1)
            effective_per_item = (price - point) / quantity
            item_infos.append({
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

        # ヒット順に並び替え & 情報登録
        item_infos = sorted(item_infos, key=lambda x: x['effective_per_item'])[:3]
        for idx2, entry in enumerate(item_infos, start=1):
            for key, value in entry.items():
                info[f"{key}_{idx2}"] = value
        for idx2 in range(len(item_infos) + 1, 4):
            for field in ['rakuten_cost', 'rakuten_point_rate', 'rakuten_point',
                          'rakuten_postage_flag', 'rakuten_effective_cost',
                          'rakuten_quantity', 'rakuten_effective_cost_per_item',
                          'rakuten_url']:
                info[f"{field}_{idx2}"] = None

        time.sleep(sleep_time)

    return asins


def extract_product_code_candidates(title):
    # 英字+数字や型番っぽい部分列を抽出（必要に応じカスタマイズ）
    if not title:
        return []
    return list(set(re.findall(r'\b[A-Z0-9\-]{4,}\b', title)))


def search_rakuten_product_api(code):
    app_id = os.getenv('RAKUTEN_API_ID')
    sleep_time = int(os.getenv('RAKUTEN_SLEEP_TIME', 1))

    url = "https://app.rakuten.co.jp/services/api/Product/Search/20170426"
    params = {
        'applicationId': app_id,
        'keyword': code,
        'hits': 10,
    }
    try:
        res = requests.get(url, params=params)
        if res.status_code == 200:
            data = res.json()
            return data.get('Products', [])
    except Exception as ve:
        logger.error('[楽天Product/Searchエラー] %s → %s', code, ve)
    finally:
        time.sleep(sleep_time)
    return []


def search_ichiba_from_product(jan=None, code=None, product_id=None):
    app_id = os.getenv('RAKUTEN_API_ID')
    sleep_time = int(os.getenv('RAKUTEN_SLEEP_TIME', 1))

    url = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20170706"
    params = {
        'applicationId': app_id,
        'hits': 10,
        'field': 0,
        'sort': '+itemPrice',
        'availability': 1,
    }
    if jan:
        params['keyword'] = jan
    elif code:
        params['keyword'] = code
    elif product_id:
        params['productId'] = product_id
    else:
        return []
    try:
        res = requests.get(url, params=params)
        if res.status_code == 200:
            data = res.json()
            return data.get('Items', [])
    except Exception as ve:
        logger.error('[楽天IchibaItem/Searchエラー] %s %s %s → %s', code, jan, product_id, ve)
    finally:
        time.sleep(sleep_time)
    return []

    # 下は旧実装（コメント）の print も logger に変えてある。必要になったら復活して使えるようにしておく。
    # for asin, info in asins.items():
    #     if info is None:
    #         logger.info("[楽天SKIP] ASIN=%s → infoがNone", asin)
    #         continue
    #
    #     title = (info.get('title') or '').strip()
    #     jan = (info.get('jan') or '').strip()
    #     brand = (info.get('brand') or '').strip()
    #     model = (info.get('model') or '').strip()
    #     fallback = jan if len(jan) >= 4 else asin
    #
    #     item_infos = []
    #     items = []
    #
    #     # 検索パターンリスト組み立て: 優先順に重複無しで
    #     search_patterns = []
    #     if jan and len(jan) >= 7:
    #         search_patterns.append(jan)
    #     if brand and model:
    #         search_patterns.append(f"{brand} {model}")
    #     if model:
    #         search_patterns.append(model)
    #     # タイトル特徴語ごと単体
    #     feature_words = extract_feature_words(title)
    #     for w in feature_words:
    #         if w not in search_patterns:
    #             search_patterns.append(w)
    #     # 除重
    #     search_patterns = [w for i, w in enumerate(search_patterns) if w and w not in search_patterns[:i]]
    #
    #     # パターンごと探索
    #     hit_flag = False
    #     for keyword in search_patterns:
    #         logger.info("[楽天多段検索] keyword=%s", keyword)
    #         try:
    #             items = perform_rakuten_api_search(keyword, app_id)
    #         except Exception as ve:
    #             logger.warning("[楽天SKIP] ASIN=%s → keyword=%s エラー: %s", asin, keyword, ve)
    #             items = []
    #         time.sleep(sleep_time)
    #         if items:
    #             hit_flag = True
    #             break  # 最初にヒットしたパターン（最大3件）で抜ける
    #
    #     # 結果処理（item_infosへの記録）
    #     if not items:
    #         logger.info("[楽天NO_HIT] ASIN=%s, fallback=%s", asin, fallback)
    #
    #     for item in items[:3]:
    #         t_title = item.get('itemName') or ""
    #         caption = item.get('itemCaption', "")
    #         if is_used_product(t_title, caption):
    #             continue
    #         if any(kw in t_title for kw in EXCLUDE_KEYWORDS):
    #             continue
    #
    #         price = float(item.get('itemPrice', 0))
    #         point_rate = float(item.get('pointRate', 0)) / 100
    #         point = int(price * point_rate)
    #         quantity = extract_quantity_from_rakuten_title(t_title)
    #         quantity = max(quantity, 1)
    #         effective_per_item = (price - point) / quantity
    #         item_infos.append({
    #             'effective_per_item': effective_per_item,
    #             'rakuten_cost': price,
    #             'rakuten_point_rate': point_rate,
    #             'rakuten_point': point,
    #             'rakuten_postage_flag': int(item.get('postageFlag', 0)),
    #             'rakuten_effective_cost': price - point,
    #             'rakuten_quantity': quantity,
    #             'rakuten_effective_cost_per_item': effective_per_item,
    #             'rakuten_url': item.get('itemUrl')
    #         })
    #
    #     # ヒット順に並び替え＆情報登録（最大3件）
    #     item_infos = sorted(item_infos, key=lambda x: x['effective_per_item'])[:3]
    #     for idx, entry in enumerate(item_infos, start=1):
    #         for key, value in entry.items():
    #             info[f"{key}_{idx}"] = value
    #     for idx in range(len(item_infos) + 1, 4):
    #         for field in ['rakuten_cost', 'rakuten_point_rate', 'rakuten_point',
    #                       'rakuten_postage_flag', 'rakuten_effective_cost',
    #                       'rakuten_quantity', 'rakuten_effective_cost_per_item',
    #                       'rakuten_url']:
    #             info[f"{field}_{idx}"] = None
    #
    #     time.sleep(sleep_time)
    #
    # return asins


def extract_feature_words(txt):
    """
    タイトルから特徴的な単語（メーカー名/型番以外の固有ワードなど）を抽出
    """
    if not txt:
        return []
    tokens = re.findall(r'[A-Za-z0-9\-/.]+|[一-龥]{2,}|[ァ-ヴー]{2,}', txt)
    return [t for t in tokens if len(t) >= 2]
