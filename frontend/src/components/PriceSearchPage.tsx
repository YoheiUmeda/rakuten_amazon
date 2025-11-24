// src/components/PriceSearchPage.tsx
import React, { useState } from "react";
import { fetchPrices, PriceItem } from "../api/prices";

const formatYen = (value: number | null | undefined): string => {
  if (value == null) return "-";
  return Math.round(value).toLocaleString();
};

const formatPercent = (value: number | null | undefined): string => {
  if (value == null) return "-";
  return value.toFixed(1);
};

const PriceSearchPage: React.FC = () => {
  const [keyword, setKeyword] = useState("");
  const [minProfit, setMinProfit] = useState("");
  const [minRoi, setMinRoi] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [items, setItems] = useState<PriceItem[]>([]);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const result = await fetchPrices({
        keyword: keyword || undefined,
        min_profit: minProfit ? Number(minProfit) : undefined,
        min_roi: minRoi ? Number(minRoi) : undefined,
        limit: 50,
      });
      setItems(result);
    } catch (err: any) {
      console.error(err);
      setError(err.message ?? "エラーが発生しました");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: "16px", maxWidth: 1100, margin: "0 auto" }}>
      <h1>価格差チェック</h1>

      <form onSubmit={handleSearch} style={{ marginBottom: "16px" }}>
        <div style={{ marginBottom: "8px" }}>
          <label>
            キーワード：
            <input
              type="text"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              style={{ marginLeft: 8 }}
            />
          </label>
        </div>

        <div style={{ marginBottom: "8px" }}>
          <label>
            最低利益（円）：
            <input
              type="number"
              value={minProfit}
              onChange={(e) => setMinProfit(e.target.value)}
              style={{ marginLeft: 8 }}
            />
          </label>
        </div>

        <div style={{ marginBottom: "8px" }}>
          <label>
            最低ROI（%）：
            <input
              type="number"
              value={minRoi}
              onChange={(e) => setMinRoi(e.target.value)}
              style={{ marginLeft: 8 }}
            />
          </label>
        </div>

        <button type="submit" disabled={loading}>
          {loading ? "検索中..." : "検索する"}
        </button>
      </form>

      {error && (
        <div style={{ color: "red", marginBottom: "8px" }}>エラー：{error}</div>
      )}

      <table
        style={{
          width: "100%",
          borderCollapse: "collapse",
          fontSize: "14px",
        }}
      >
        <thead>
          <tr>
            <th>ASIN</th>
            <th>タイトル</th>
            <th>Amazon価格</th>
            <th>楽天価格</th>
            <th>利益</th>
            <th>ROI %</th>
            <th>リンク</th> {/* 🔽 追加 */}
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.asin}>
              <td style={{ borderBottom: "1px solid #eee" }}>{item.asin}</td>
              <td style={{ borderBottom: "1px solid #eee" }}>
                {item.title ?? "-"}
              </td>
              <td
                style={{
                  borderBottom: "1px solid #eee",
                  textAlign: "right",
                }}
              >
                {formatYen(item.amazon_price)}
              </td>
              <td
                style={{
                  borderBottom: "1px solid #eee",
                  textAlign: "right",
                }}
              >
                {formatYen(item.rakuten_price)}
              </td>
              <td
                style={{
                  borderBottom: "1px solid #eee",
                  textAlign: "right",
                }}
              >
                {formatYen(item.profit_per_item)}
              </td>
              <td
                style={{
                  borderBottom: "1px solid #eee",
                  textAlign: "right",
                }}
              >
                {formatPercent(item.roi_percent)}
              </td>
              {/* 🔽 リンク列 */}
              <td
                style={{
                  borderBottom: "1px solid #eee",
                  textAlign: "center",
                  whiteSpace: "nowrap",
                }}
              >
                {item.amazon_url && (
                  <a
                    href={item.amazon_url}
                    target="_blank"
                    rel="noreferrer"
                    style={{ marginRight: 8 }}
                  >
                    Amazon
                  </a>
                )}
                {item.rakuten_url && (
                  <a href={item.rakuten_url} target="_blank" rel="noreferrer">
                    楽天
                  </a>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default PriceSearchPage;