import re
import spacy

# 日本語spaCyモデル（要インストール: pip install ja_core_news_sm）
nlp = spacy.load("ja_core_news_sm")

# 除外対象単位や文脈（スペック・容量・世代など）
EXCLUDE_CONTEXT = ['GB', 'TB', 'GHz', 'インテル', '世代', 'インチ', 'プロセッサ', 'Windows', 'Office', 'Hz', 'ms']

# 数量にありがちなコンテキスト
INCLUDE_HINT = ['個', '本', '枚', 'pcs', 'セット', '入り', 'パック', 'x', '×', 'box']

# 型番に該当しやすいパターン（英数字混合 → CF-LX6, ST14000NM001G, etc.）
MODEL_PATTERNS = [
    r'[A-Z]{2,5}[-_]?[A-Z0-9]{2,}',       # CF-LX6, ST-100ABC など
    r'[A-Z]{2,}-?\d{3,}',                # AA-1234, XX12345
    r'[A-Z]{2,5}[-_]?[\d]{2,5}[A-Z0-9\-]{2,}',  # ← 例: DM25-EX1
    r'[A-Z0-9]{5,}-?\d{2,}',             # ST14000NM001G
]

# 型番としてよくあるキーワード（ブランド依存で自由に追加できる）
MODEL_KEYWORDS = [
    'CF-', 'LX', 'SV', 'PC-', 'dynabook', 'versapro', 'optiplex', 'vostro', 'R73'
]

#general
def is_likely_model_number(text: str) -> bool:
    """
    型番らしい文字列かどうか（数量ではないかどうか）を判定
    """
    # 大文字小文字統一
    lower_text = text.lower()

    # パターンマッチ
    for pattern in MODEL_PATTERNS:
        if re.search(pattern, lower_text):
            return True

    # 特定キーワードが含まれていれば型番らしいと判定
    for keyword in MODEL_KEYWORDS:
        if keyword.lower() in lower_text:
            return True

    return False

def clean_text_before_extract(raw_text):
    """
    数量抽出前にテキストを事前クリーンアップして誤認識を防ぐ（特に縦横(cm)サイズ）
    """
    text = raw_text

    # ✅ 縦横サイズの除去（例：3m×2m、305×76cm）
    text = re.sub(r'\b\d{1,4}\s*[×xｘX＊*]\s*\d{1,4}(\.\d+)?\s*(cm|mm|インチ|m)?\b', '', text, flags=re.IGNORECASE)

    # ✅ 単独サイズ表現の除去（例：75cm、3m）
    text = re.sub(r'\b\d{1,4}(\.\d+)?\s*(cm|mm|m|インチ|inch)\b', '', text, flags=re.IGNORECASE)

    # ✅ 倍率表現の除去（例：40X-2000X、倍率40xなど）
    text = re.sub(r'\b倍率\s*\d+[×xｘX＊*‐―-]\d+\b', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\b\d+[×xｘX＊*‐―-]\d+\b', '', text, flags=re.IGNORECASE)  # fallback for spaCy先にも入れてOK

    return text

#amazon
def is_likely_quantity(ent_text: str, original_text: str) -> bool:
    # ここも型番チェック追加すると安全（二重チェック）
    if is_likely_model_number(ent_text):
        return False
    for ex_kw in EXCLUDE_CONTEXT:
        if ex_kw.lower() in ent_text.lower():
            return False

    window = 10
    match = re.search(re.escape(ent_text), original_text)
    if match:
        start = max(0, match.start() - window)
        end = match.end() + window
        surrounding = original_text[start:end]
        if any(hint in surrounding for hint in INCLUDE_HINT):
            return True

    return False

def extract_quantity_nlp(text: str) -> int | None:
    doc = nlp(text)
    candidates = []

    for ent in doc.ents:
        if ent.label_ == "QUANTITY":
            # 型番のような文字列は数量として無視
            if is_likely_model_number(ent.text):
                continue

            value = re.search(r'\d+', ent.text)
            if value:
                qty = int(value.group())
                if 0 < qty < 100 and is_likely_quantity(ent.text, text):
                    candidates.append(qty)

    return max(candidates) if candidates else None

# 🧠 最終統合処理：NLP + 正規表現 + fallback
def extract_quantity_combined(text: str) -> int:
    text = clean_text_before_extract(text)
    q_nlp = extract_quantity_nlp(text)
    if q_nlp:
        return q_nlp

    q_regex = extract_quantity_from_text(text)
    if q_regex:
        return q_regex

    return 1  # フォールバック：明示的な数量がなければ1


def extract_quantity_from_text(text: str) -> int | None:
    if not text:
        return 1

    # ✅ 「パック入り」「パック入」が含まれていれば無条件に除外（数量1とみなす）
    if re.search(r'\d+\s*(パック入|パック入り|pack in|pack入り)', text.lower()):
        return 1  # 抽出せず → fallbackで数量1へ

    # ✅ 通常の除外ワードチェック
    excluded_context = ['gb', 'ghz', 'rpm', '年', '保証', 'tb', 'nas', 'cmr']
    for ex in excluded_context:
        if ex.lower() in text.lower():
            return 1

    patterns = [
        r'(\d+)\s*本セット',
        r'(\d+)\s*個セット',
        r'(\d+)\s*枚セット',
        r'(\d+)\s*個入',
        r'(\d+)\s*枚入',
        r'(\d+)\s*pcs',
        r'(\d+)\s*パック',
        r'(\d+)\s*セット',
        r'set\s*of\s*(\d+)',
        r'[×xｘX＊*]\s*(\d+)',
        r'(\d+)\s*pack',
        r'(\d+)\s*本\b',
        r'(\d+)\s*個\b',
        r'(\d+)\s*枚入り',
        r'(\d+)\s*枚\b',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            match_text = match.group(0)
            if is_likely_model_number(match_text):
                continue
            try:
                quantity = int(match.group(1))
                if 0 < quantity < 100:
                    return quantity
            except ValueError:
                continue

    return 1

#rakuten
def is_valid_quantity(entity_text: str, original_text: str) -> bool:
    if is_likely_model_number(entity_text):
        return False

    for kw in EXCLUDE_CONTEXT:
        if kw in entity_text.lower():
            return False

    match = re.search(re.escape(entity_text), original_text)
    if match:
        window = 10
        start = max(0, match.start() - window)
        end = match.end() + window
        surrounding = original_text[start:end]

        # ✅ 除外ワードチェック（box が含まれるようにする）
        exclude_words = ['倍率', 'box', 'パック未開封', '個包装', 'カートン', '未開封']
        if any(word in surrounding for word in exclude_words):
            return False
        
        print(f"[DEBUG] QUANTITY={entity_text} → surrounding: '{surrounding}'")

        if any(hint in surrounding for hint in INCLUDE_HINT):
            return True

    return False

def extract_quantity(title: str) -> int:
    """シンプルな正規表現ベースの数量抽出（パック入り除外あり）"""
    patterns = [
        r'(\d+)\s*個\s*(入り|セット)?',
        r'[×ｘxX＊*]\s*(\d+)',
        r'(\d+)\s*(本|枚|袋|パック|箱|セット)',
    ]
    for pattern in patterns:
        match = re.search(pattern, title)
        if match:
            text_fragment = match.group(0)

            # ✅ 型番と思われる場合は除外
            if is_likely_model_number(text_fragment):
                continue

            # ✅ 「パック入り」などは除外対象とする
            if re.search(r'パック入り|パック入|pack in', text_fragment, re.IGNORECASE):
                continue

            try:
                return int(match.group(1))
            except:
                continue

    return 1  # fallback

def extract_quantity_from_rakuten_title(title: str) -> int:
    """
    楽天の商品名から数量を抽出（spaCy + 除外ルール + パターンマッチ）
    """

    title = clean_text_before_extract(title)
    title = title.lower()

    # ✅ 「パック入り」「パック入」が含まれていれば無条件に除外（数量1とみなす）
    if re.search(r'\d+\s*(パック入|パック入り|pack in|pack入り)', title):
        return 1  # 抽出せず → fallbackで数量1へ

    # ✅ 1. 除外ワード（DVD/CD/特典/選べる etc）
    media_combo_keywords = [
        "blu-ray＋dvd", "blu-ray+dvd", "ブルーレイ＋dvd", "ブルーレイ+dvd",
        "blu-ray&dvd", "ブルーレイ&dvd", "blu-ray/dvd", "ブルーレイ/dvd",
        "コンボパック", "combo pack", "2枚組", "限定盤", "特典付き", "dual", "選べる"
    ]
    if any(k in title for k in media_combo_keywords):
        return 1

    # ✅ 2. スペックなどの除外数値（12インチ, 75Hzなど）
    exclusion_pattern = r'\d+\s*(%s)' % "|".join(EXCLUDE_CONTEXT)
    title = re.sub(exclusion_pattern, '', title, flags=re.IGNORECASE)

    # ✅ 3. ポイントなどの販促ワード除去
    title = re.sub(r'(ポイント\s*\d+倍|p\d+倍|\d+倍)', '', title, flags=re.IGNORECASE)

    # ✅ 4. spaCyの固有表現（QUANTITY）から候補取得
    doc = nlp(title)
    quantity_candidates = []

    for ent in doc.ents:
        if ent.label_ == "QUANTITY":
            if is_likely_model_number(ent.text):
                continue
            number = re.search(r'\d+', ent.text)
            if number:
                qty = int(number.group())
                if 0 < qty < 100 and is_valid_quantity(ent.text, title):
                    quantity_candidates.append(qty)

    # ✅ 5. 正規表現補完パターン
    quantity_patterns = [
        r'(\d+)\s*個\s*(入|入り|セット)?',
        r'[×xｘX＊*]\s*(\d+)',
        r'(\d+)\s*(本|袋|箱|パック|セット|枚)',
        r'(\d+)\s*個'
    ]
    for pattern in quantity_patterns:
        match = re.search(pattern, title)
        if match:
            text_fragment = match.group(0)
            if is_likely_model_number(text_fragment):
                continue
            try:
                quantity_candidates.append(int(match.group(1)))
            except:
                continue

    # ✅ 6. 優先判定（最大値 or 最初の値などにカスタマイズ可）
    if quantity_candidates:
        # 同一数値の重複を排除
        unique_candidates = list(set(quantity_candidates))
        return max(unique_candidates)

    return 1  # fallback when no quantity found