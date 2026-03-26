import os
import re
import urllib.parse
import requests
import time
import logging
import json
from dotenv import load_dotenv
from typing import Dict

_RAKUTEN_TIMEOUT = (10, 30)  # (connect_timeout, read_timeout) 秒

# .envからAPIキー読込など
load_dotenv(override=True)
logger = logging.getLogger(__name__)

EXCLUDE_KEYWORDS = [
    "保証", "延長", "修理", "保護", "フィルム",
    "チケット", "サービス", "まとめ買い", "セット内容", "オプション"
]

# 対象外ショップ（例：楽天Kobo電子書籍など）
EXCLUDE_SHOP_SUBSTRINGS = [
    "rakutenkobo-ebooks",
]

# 楽天側の「価格が安すぎる」商品を除外する下限（誤マッチ対策）
MIN_RAKUTEN_PRICE = float(os.getenv("MIN_RAKUTEN_PRICE", "0"))

# 検証用：深い検索をスキップするフラグ
FAST_MODE = os.getenv("RAKUTEN_FAST_MODE", "0") == "1"

# シンプルなディスクキャッシュ
RAKUTEN_CACHE_PATH = os.getenv("RAKUTEN_CACHE_PATH", "rakuten_cache.json")
try:
    with open(RAKUTEN_CACHE_PATH, "r", encoding="utf-8") as f:
        RAKUTEN_CACHE: Dict[str, list] = json.load(f)
    logger.info("[楽天CACHE] 読込成功 path=%s entries=%d", RAKUTEN_CACHE_PATH, len(RAKUTEN_CACHE))
except FileNotFoundError:
    RAKUTEN_CACHE = {}
    logger.info("[楽天CACHE] ファイルなし → 新規作成 path=%s", RAKUTEN_CACHE_PATH)
except Exception as e:
    RAKUTEN_CACHE = {}
    logger.error("[楽天CACHE読込エラー] %s", e)


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
    max_retries = int(os.getenv("RAKUTEN_MAX_RETRIES", "3"))
    params = {
        'applicationId': app_id,
        'keyword': keyword,
        'hits': int(os.getenv("RAKUTEN_HITS", "10")),  # デフォルト10件程度
        'sort': '+itemPrice',
        'field': 0,
        'availability': 1
    }
    logger.debug(f"[RakutenAPI] keyword={keyword} params={params}")

    for attempt in range(max_retries):
        is_last = (attempt + 1 == max_retries)
        try:
            r = requests.get(url, params=params, timeout=_RAKUTEN_TIMEOUT)

            is_rate_limited = (
                r.status_code == 429
                or ('error' in r.text and 'too_many_requests' in r.text)
            )
            if is_rate_limited:
                if is_last:
                    logger.error(
                        "[RakutenAPI] rate_limit 最大試行回数(%d)超過 keyword=%s",
                        max_retries, keyword,
                    )
                    return []
                wait = 10 * (attempt + 1)
                logger.warning(
                    "[RakutenAPI] rate_limit attempt=%d/%d wait=%ds keyword=%s",
                    attempt + 1, max_retries, wait, keyword,
                )
                time.sleep(wait)
                continue

            if r.status_code != 200:
                logger.error("[RakutenAPI] HTTP %s keyword=%s", r.status_code, keyword)
                return []

            js = r.json()
            if "error" in js:
                if js["error"] == "too_many_requests":
                    if is_last:
                        logger.error(
                            "[RakutenAPI] rate_limit 最大試行回数(%d)超過 keyword=%s",
                            max_retries, keyword,
                        )
                        return []
                    wait = 10 * (attempt + 1)
                    logger.warning(
                        "[RakutenAPI] rate_limit attempt=%d/%d wait=%ds keyword=%s",
                        attempt + 1, max_retries, wait, keyword,
                    )
                    time.sleep(wait)
                    continue
                logger.error("[RakutenAPI] APIエラー error=%s keyword=%s", js["error"], keyword)
                return []

            items = js.get('Items', [])
            logger.info("[RakutenAPI] keyword=%s hit=%d件", keyword, len(items))
            return [itemBlock['Item'] for itemBlock in items]

        except requests.exceptions.Timeout:
            if is_last:
                logger.error(
                    "[RakutenAPI] timeout 最大試行回数(%d)超過 keyword=%s",
                    max_retries, keyword,
                )
                return []
            wait = 10 * (attempt + 1)
            logger.warning(
                "[RakutenAPI] timeout attempt=%d/%d wait=%ds keyword=%s",
                attempt + 1, max_retries, wait, keyword,
            )
            time.sleep(wait)
            continue
        except Exception as e:
            logger.error("[RakutenAPI] 例外 keyword=%s → %s", keyword, e)
            return []

    return []


def perform_rakuten_api_search_from_itemcode(itemcode: str, app_id: str):
    """API呼出し（エラーハンドリング付・結果返却）"""
    url = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20170706"
    max_retries = int(os.getenv("RAKUTEN_MAX_RETRIES", "3"))
    params = {
        'applicationId': app_id,
        'itemCode': itemcode,
        'hits': 20,
        'sort': '+itemPrice',
        'field': 0,
        'availability': 0
    }
    for attempt in range(max_retries):
        is_last = (attempt + 1 == max_retries)
        try:
            r = requests.get(url, params=params, timeout=_RAKUTEN_TIMEOUT)

            is_rate_limited = (
                r.status_code == 429
                or ('error' in r.text and 'too_many_requests' in r.text)
            )
            if is_rate_limited:
                if is_last:
                    logger.error(
                        "[楽天API] rate_limit 最大試行回数(%d)超過 itemcode=%s",
                        max_retries, itemcode,
                    )
                    return []
                wait = 10 * (attempt + 1)
                logger.warning(
                    "[楽天API] rate_limit attempt=%d/%d wait=%ds itemcode=%s",
                    attempt + 1, max_retries, wait, itemcode,
                )
                time.sleep(wait)
                continue

            if r.status_code != 200:
                logger.error("[楽天APIエラー] status=%s itemcode=%s", r.status_code, itemcode)
                return []

            js = r.json()
            if "error" in js:
                if js["error"] == "too_many_requests":
                    if is_last:
                        logger.error(
                            "[楽天API] rate_limit 最大試行回数(%d)超過 itemcode=%s",
                            max_retries, itemcode,
                        )
                        return []
                    wait = 10 * (attempt + 1)
                    logger.warning(
                        "[楽天API] rate_limit attempt=%d/%d wait=%ds itemcode=%s",
                        attempt + 1, max_retries, wait, itemcode,
                    )
                    time.sleep(wait)
                    continue
                logger.error("[楽天APIエラー] error=%s itemcode=%s", js["error"], itemcode)
                return []

            items = js.get('Items', [])
            return [itemBlock['Item'] for itemBlock in items]

        except requests.exceptions.Timeout:
            if is_last:
                logger.error(
                    "[楽天API] timeout 最大試行回数(%d)超過 itemcode=%s",
                    max_retries, itemcode,
                )
                return []
            wait = 10 * (attempt + 1)
            logger.warning(
                "[楽天API] timeout attempt=%d/%d wait=%ds itemcode=%s",
                attempt + 1, max_retries, wait, itemcode,
            )
            time.sleep(wait)
            continue
        except Exception as e:
            logger.error("[楽天APIエラー/例外] itemcode=%s → %s", itemcode, e)
            return []

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
        cache_key = fallback

        item_infos = []
        items = []

        # まずキャッシュチェック
        if cache_key in RAKUTEN_CACHE:
            cached_entries = RAKUTEN_CACHE[cache_key] or []
            logger.info("[楽天CACHE HIT] key=%s entries=%d", cache_key, len(cached_entries))

            # キャッシュ内容を info に展開
            for idx2, entry in enumerate(cached_entries[:3], start=1):
                for key, value in entry.items():
                    info[f"{key}_{idx2}"] = value
            for idx2 in range(len(cached_entries) + 1, 4):
                for field in ['rakuten_cost', 'rakuten_point_rate', 'rakuten_point',
                              'rakuten_postage_flag', 'rakuten_effective_cost',
                              'rakuten_quantity', 'rakuten_effective_cost_per_item',
                              'rakuten_url']:
                    info[f"{field}_{idx2}"] = None

            # キャッシュヒット時はAPI呼び出しなしで次のASINへ
            continue

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

        # FAST_MODE の場合はここまで（JAN/タイトル）で諦める
        if not items and FAST_MODE:
            logger.info("[Rakuten FAST_MODE] ASIN=%s key=%s 深い検索スキップ", asin, cache_key)

        # ③ 商品番号候補抽出→IchibaItemSearch（FAST_MODEでは実行しない）
        if not items and not FAST_MODE:
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
                time.sleep(sleep_time)

        # ② JANでNO_HIT→メーカー名＋型番で検索（FAST_MODEでは実行しない）
        if not items and not FAST_MODE:
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

        # ❸ 型番等 短縮キーワード最終検索（FAST_MODEでは実行しない）
        if not items and not FAST_MODE:
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

            item_url = item.get("itemUrl") or ""
            item_code = item.get("itemCode") or ""
            shop_name = item.get("shopName") or ""

            # ① Kobo/電子書籍系など、明らかに対象外のショップを除外
            if any(s in item_url for s in EXCLUDE_SHOP_SUBSTRINGS) or any(
                s in item_code for s in EXCLUDE_SHOP_SUBSTRINGS
            ):
                logger.info(
                    "[楽天除外] 電子書籍系ショップ itemCode=%s shopName=%s url=%s",
                    item_code,
                    shop_name,
                    item_url,
                )
                continue

            # 中古・訳ありなどは除外
            if is_used_product(title, caption):
                continue
            # タイトルNGワードで除外
            if any(kw in title for kw in EXCLUDE_KEYWORDS):
                continue

            # ② 価格取得
            try:
                price = float(item.get('itemPrice', 0) or 0)
            except Exception:
                logger.warning("[楽天除外] 価格が数値に変換できない itemCode=%s", item_code)
                continue

            # 0円 or マイナスは明らかに異常
            if price <= 0:
                logger.debug("[楽天除外] 価格が0以下 itemCode=%s price=%s", item_code, price)
                continue

            # ③ 楽天価格が異常に安いものを除外（誤マッチ対策）
            if MIN_RAKUTEN_PRICE > 0 and price < MIN_RAKUTEN_PRICE:
                logger.debug(
                    "[楽天除外] 価格が下限未満 itemCode=%s price=%s threshold=%s",
                    item_code,
                    price,
                    MIN_RAKUTEN_PRICE,
                )
                continue

            point_rate = float(item.get('pointRate', 0) or 0) / 100
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
                'rakuten_url': item_url
            })

        # ヒット順に並び替え & 情報登録（最大3件）
        item_infos = sorted(item_infos, key=lambda x: x['effective_per_item'])[:3]

        # キャッシュに保存（NO_HITでも空配列としてキャッシュ）
        RAKUTEN_CACHE[cache_key] = item_infos

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

    # ループ完了後にキャッシュを書き出し
    try:
        with open(RAKUTEN_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(RAKUTEN_CACHE, f, ensure_ascii=False)
        logger.info("[楽天CACHE] 保存完了 path=%s entries=%d", RAKUTEN_CACHE_PATH, len(RAKUTEN_CACHE))
    except Exception as e:
        logger.error("[楽天CACHE保存エラー] %s", e)

    return asins


def extract_product_code_candidates(title):
    # 英字+数字や型番っぽい部分列を抽出（必要に応じカスタマイズ）
    if not title:
        return []
    return list(set(re.findall(r'\b[A-Z0-9\-]{4,}\b', title)))


def search_rakuten_product_api(code):
    app_id = os.getenv('RAKUTEN_API_ID')
    sleep_time = float(os.getenv('RAKUTEN_SLEEP_TIME', 1))

    url = "https://app.rakuten.co.jp/services/api/Product/Search/20170426"
    params = {
        'applicationId': app_id,
        'keyword': code,
        'hits': 10,
    }
    try:
        res = requests.get(url, params=params, timeout=_RAKUTEN_TIMEOUT)
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
    sleep_time = float(os.getenv('RAKUTEN_SLEEP_TIME', 1))

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
        res = requests.get(url, params=params, timeout=_RAKUTEN_TIMEOUT)
        if res.status_code == 200:
            data = res.json()
            return data.get('Items', [])
    except Exception as ve:
        logger.error('[楽天IchibaItem/Searchエラー] %s %s %s → %s', code, jan, product_id, ve)
    finally:
        time.sleep(sleep_time)
    return []


def extract_feature_words(txt):
    """
    タイトルから特徴的な単語（メーカー名/型番以外の固有ワードなど）を抽出
    """
    if not txt:
        return []
    tokens = re.findall(r'[A-Za-z0-9\-/.]+|[一-龥]{2,}|[ァ-ヴー]{2,}', txt)
    return [t for t in tokens if len(t) >= 2]
