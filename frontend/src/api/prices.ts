// src/api/prices.ts

// 🔍 検索条件
export interface PriceSearchCondition {
  keyword?: string;
  min_profit?: number;
  min_roi?: number;
  limit?: number;
  only_pass_filter?: boolean; // pass_filter=true だけ欲しいとき用
}

// 🔍 1件分の結果
export interface PriceItem {
  asin: string;
  title: string;
  amazon_price: number | null;
  rakuten_price: number | null;
  profit_per_item: number | null; // ← これがあること
  roi_percent: number | null;
  diff: number | null;
  pass_filter: boolean;
  checked_at: string;
  amazon_url: string;
  rakuten_url: string;
}

// 🔍 一覧のレスポンス
export interface PriceResponse {
  items: PriceItem[];
  total: number;
}

// 🔍 サマリ情報
export interface PriceSummary {
  latest_checked_at: string | null;
  count: number;
  avg_profit: number | null;
  avg_roi: number | null;
}

// 🔍 バッチ実行レスポンス
export interface RunJobResponse {
  status: string;
  files?: number;
  total_asins?: number;
  asin_count?: number;
  excel_path?: string;
}

const BASE_URL = "http://127.0.0.1:8000";

// 価格一覧取得（条件付き）
export async function fetchPrices(
  condition: PriceSearchCondition
): Promise<PriceItem[]> {
  const res = await fetch(`${BASE_URL}/api/prices`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(condition),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error: ${res.status} ${text}`);
  }

  const data: PriceResponse = await res.json();
  return data.items;
}

// サマリー取得（※エンドポイントが無ければ null を返す）
export async function fetchPriceSummary(): Promise<PriceSummary | null> {
  const res = await fetch(`${BASE_URL}/api/prices/summary`);

  // FastAPI 側にエンドポイント未実装なら 404 になる。
  // その場合は「サマリーなし」として扱い、フロントで何も表示しない。
  if (res.status === 404) {
    return null;
  }

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error: ${res.status} ${text}`);
  }

  const data: PriceSummary = await res.json();
  return data;
}

// バッチ実行（Keepa→DB→Excel）
export async function runPricesJob(): Promise<RunJobResponse> {
  const res = await fetch(`${BASE_URL}/api/prices/run`, {
    method: "POST",
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error: ${res.status} ${text}`);
  }

  const data: RunJobResponse = await res.json();
  return data;
}
