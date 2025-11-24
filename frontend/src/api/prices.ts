// src/api/prices.ts
export interface PriceSearchCondition {
  keyword?: string;
  min_profit?: number;
  min_roi?: number;
  limit?: number;
}

export interface PriceItem {
  asin: string;
  title: string | null;
  amazon_price: number | null;
  rakuten_price: number | null;
  profit_per_item: number | null;
  roi_percent: number | null;
  checked_at: string;
  // 🔽 ここ追加
  amazon_url: string | null;
  rakuten_url: string | null;
}

export interface PriceResponse {
  items: PriceItem[];
}

const BASE_URL = "http://127.0.0.1:8000"; // or localhost:8000

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
