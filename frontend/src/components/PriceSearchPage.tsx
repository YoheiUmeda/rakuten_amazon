// src/components/PriceSearchPage.tsx
import React, { useMemo, useState } from "react";
import {
  fetchPrices,
  fetchPriceSummary,
  runPricesJob,
  PriceItem,
  PriceSearchCondition,
  PriceSummary,
  RunJobResponse,
} from "../api/prices";

const formatYen = (value: number | null | undefined): string => {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return value.toLocaleString("ja-JP", {
    style: "currency",
    currency: "JPY",
    maximumFractionDigits: 0,
  });
};

const formatPercent = (value: number | null | undefined): string => {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return `${value.toFixed(1)}%`;
};

const PriceSearchPage: React.FC = () => {
  // ====== 検索条件 ======
  const [condition, setCondition] = useState<PriceSearchCondition>({
    keyword: "",
    min_profit: undefined,
    min_roi: undefined,
    limit: 50,
    only_pass_filter: false,
  });

  // ====== 一覧・サマリ ======
  const [items, setItems] = useState<PriceItem[]>([]);
  const [summary, setSummary] = useState<PriceSummary | null>(null);

  const [isLoading, setIsLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  // 並び替え
  const [sortKey, setSortKey] = useState<keyof PriceItem | "">("");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");

  // ====== バッチ実行 ======
  const [runningJob, setRunningJob] = useState<RunJobResponse | null>(null);
  const [jobLoading, setJobLoading] = useState(false);
  const [jobError, setJobError] = useState<string | null>(null);

  // ====== 検索条件のハンドラ ======
  const handleChangeKeyword = (
    e: React.ChangeEvent<HTMLInputElement>
  ): void => {
    const value = e.target.value;
    setCondition((prev) => ({ ...prev, keyword: value }));
  };

  const handleChangeNumber =
    (field: "min_profit" | "min_roi" | "limit") =>
    (e: React.ChangeEvent<HTMLInputElement>): void => {
      const value = e.target.value;
      setCondition((prev) => ({
        ...prev,
        [field]: value === "" ? undefined : Number(value),
      }));
    };

  const handleChangeOnlyPassFilter = (
    e: React.ChangeEvent<HTMLInputElement>
  ): void => {
    const checked = e.target.checked;
    setCondition((prev) => ({ ...prev, only_pass_filter: checked }));
  };

  // ====== 検索実行 ======
  const handleSearch = async () => {
    setIsLoading(true);
    setLoadError(null);
    try {
      // 余計な空文字は undefined にしてサーバに渡す
      const cleaned: PriceSearchCondition = {
        keyword: condition.keyword?.trim() || undefined,
        min_profit: condition.min_profit,
        min_roi: condition.min_roi,
        limit: condition.limit,
        only_pass_filter: condition.only_pass_filter,
      };

      const [list, summaryRes] = await Promise.all([
        fetchPrices(cleaned),
        fetchPriceSummary(),
      ]);
      setItems(list);
      setSummary(summaryRes);
    } catch (e) {
      setLoadError(
        e instanceof Error
          ? e.message
          : "検索中に不明なエラーが発生しました。"
      );
    } finally {
      setIsLoading(false);
    }
  };

  // ====== バッチ実行 ======
  const handleRunJob = async () => {
    setJobLoading(true);
    setJobError(null);
    try {
      const res = await runPricesJob();
      setRunningJob(res);

      // バッチ完了後に結果を見たいなら、自動で再検索してもOK
      // await handleSearch(); ← 好みでONにしてもいい
    } catch (e) {
      setJobError(
        e instanceof Error
          ? e.message
          : "バッチ実行中に不明なエラーが発生しました。"
      );
    } finally {
      setJobLoading(false);
    }
  };

  // ====== 並び替え済み一覧 ======
  const sortedItems = useMemo(() => {
    const data = [...items];
    if (!sortKey) return data;

    data.sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];

      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;

      if (typeof av === "number" && typeof bv === "number") {
        return sortOrder === "asc" ? av - bv : bv - av;
      }

      const as = String(av);
      const bs = String(bv);
      return sortOrder === "asc"
        ? as.localeCompare(bs)
        : bs.localeCompare(as);
    });

    return data;
  }, [items, sortKey, sortOrder]);

  const sortableColumns: { key: keyof PriceItem; label: string }[] = [
    { key: "profit_per_item", label: "粗利" },
    { key: "roi_percent", label: "ROI" },
    { key: "amazon_price", label: "Amazon価格" },
    { key: "rakuten_price", label: "楽天価格" },
    { key: "checked_at", label: "チェック日時" },
  ];

  return (
    <div
      style={{
        padding: "24px",
        maxWidth: 1200,
        margin: "0 auto",
        fontFamily:
          'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      }}
    >
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 16 }}>
        価格差検索ダッシュボード
      </h1>

      {/* ====== バッチ実行エリア ====== */}
      <section
        style={{
          marginBottom: 24,
          padding: 16,
          borderRadius: 8,
          border: "1px solid #ddd",
          background: "#fafafa",
        }}
      >
        <h2 style={{ fontSize: 18, marginBottom: 8 }}>Keepaバッチ実行</h2>
        <p style={{ marginBottom: 12, fontSize: 14, color: "#555" }}>
          ローカルのバッチ（Keepa検索 → DB登録 → Excel出力）を実行します。
        </p>

        <button
          type="button"
          onClick={handleRunJob}
          disabled={jobLoading}
          style={{
            padding: "8px 16px",
            borderRadius: 4,
            border: "none",
            cursor: jobLoading ? "default" : "pointer",
            background: "#2563eb",
            color: "#fff",
            fontWeight: 600,
          }}
        >
          {jobLoading ? "実行中..." : "バッチを実行する"}
        </button>

        {jobError && (
          <div
            style={{
              marginTop: 12,
              padding: 8,
              borderRadius: 4,
              background: "#fee2e2",
              color: "#b91c1c",
              fontSize: 13,
            }}
          >
            {jobError}
          </div>
        )}

        {runningJob && (
          <div
            style={{
              marginTop: 16,
              padding: 12,
              borderRadius: 4,
              background: "#f3f4f6",
              fontSize: 14,
            }}
          >
            <div>ステータス: {runningJob.status}</div>
            {runningJob.files !== undefined && (
              <div>処理ファイル数: {runningJob.files}</div>
            )}
            {runningJob.total_asins !== undefined && (
              <div>総ASIN数: {runningJob.total_asins}</div>
            )}
            {runningJob.asin_count !== undefined && (
              <div>ヒット件数: {runningJob.asin_count} 件</div>
            )}
            {runningJob.excel_path && (
              <div style={{ marginTop: 8 }}>
                Excel出力先:
                <div>
                  <code>{runningJob.excel_path}</code>
                </div>
                <div style={{ fontSize: 12, marginTop: 4, color: "#555" }}>
                  ※ ローカルツールなので、上のパスをエクスプローラーで開いてください。
                </div>
              </div>
            )}
          </div>
        )}
      </section>

      {/* ====== 検索条件エリア ====== */}
      <section
        style={{
          marginBottom: 16,
          padding: 16,
          borderRadius: 8,
          border: "1px solid #ddd",
          background: "#fff",
        }}
      >
        <h2 style={{ fontSize: 18, marginBottom: 12 }}>検索条件</h2>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
            gap: 12,
            marginBottom: 12,
          }}
        >
          <label style={{ fontSize: 13 }}>
            キーワード
            <input
              type="text"
              value={condition.keyword ?? ""}
              onChange={handleChangeKeyword}
              style={{
                width: "100%",
                marginTop: 4,
                padding: "4px 6px",
                fontSize: 13,
              }}
              placeholder="ASIN / タイトルの一部 など"
            />
          </label>

          <label style={{ fontSize: 13 }}>
            最低粗利（円）
            <input
              type="number"
              value={condition.min_profit ?? ""}
              onChange={handleChangeNumber("min_profit")}
              style={{
                width: "100%",
                marginTop: 4,
                padding: "4px 6px",
                fontSize: 13,
              }}
            />
          </label>

          <label style={{ fontSize: 13 }}>
            最低ROI（%）
            <input
              type="number"
              value={condition.min_roi ?? ""}
              onChange={handleChangeNumber("min_roi")}
              style={{
                width: "100%",
                marginTop: 4,
                padding: "4px 6px",
                fontSize: 13,
              }}
            />
          </label>

          <label style={{ fontSize: 13 }}>
            最大件数
            <input
              type="number"
              value={condition.limit ?? ""}
              onChange={handleChangeNumber("limit")}
              style={{
                width: "100%",
                marginTop: 4,
                padding: "4px 6px",
                fontSize: 13,
              }}
            />
          </label>
        </div>

        <label style={{ fontSize: 13 }}>
          <input
            type="checkbox"
            checked={condition.only_pass_filter ?? false}
            onChange={handleChangeOnlyPassFilter}
            style={{ marginRight: 4 }}
          />
          pass_filter = true のみ取得
        </label>

        <div style={{ marginTop: 12 }}>
          <button
            type="button"
            onClick={handleSearch}
            disabled={isLoading}
            style={{
              padding: "6px 12px",
              borderRadius: 4,
              border: "1px solid #2563eb",
              background: isLoading ? "#eff6ff" : "#dbeafe",
              color: "#1d4ed8",
              cursor: isLoading ? "default" : "pointer",
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            {isLoading ? "検索中..." : "検索実行"}
          </button>
        </div>

        {loadError && (
          <div
            style={{
              marginTop: 8,
              padding: 8,
              borderRadius: 4,
              background: "#fee2e2",
              color: "#b91c1c",
              fontSize: 13,
            }}
          >
            {loadError}
          </div>
        )}

        {summary && (
          <div
            style={{
              marginTop: 12,
              padding: 8,
              borderRadius: 4,
              background: "#f3f4f6",
              fontSize: 13,
              display: "flex",
              flexWrap: "wrap",
              gap: 16,
            }}
          >
            <div>
              最新チェック:
              <br />
              <strong>{summary.latest_checked_at ?? "-"}</strong>
            </div>
            <div>
              件数:
              <br />
              <strong>{summary.count}</strong>
            </div>
            <div>
              平均粗利:
              <br />
              <strong>{formatYen(summary.avg_profit)}</strong>
            </div>
            <div>
              平均ROI:
              <br />
              <strong>{formatPercent(summary.avg_roi)}</strong>
            </div>
          </div>
        )}
      </section>

      {/* ====== 一覧表示エリア ====== */}
      <section
        style={{
          padding: 16,
          borderRadius: 8,
          border: "1px solid #ddd",
          background: "#fff",
        }}
      >
        <div
          style={{
            marginBottom: 12,
            display: "flex",
            flexWrap: "wrap",
            gap: 12,
            alignItems: "center",
          }}
        >
          <h2 style={{ fontSize: 18, margin: 0 }}>検索結果一覧</h2>

          <div
            style={{
              marginLeft: "auto",
              display: "flex",
              gap: 8,
              alignItems: "center",
              fontSize: 13,
            }}
          >
            <span>並び替え:</span>
            <select
              value={sortKey || ""}
              onChange={(e) =>
                setSortKey(
                  e.target.value === ""
                    ? ""
                    : (e.target.value as keyof PriceItem)
                )
              }
              style={{ padding: 4, fontSize: 13 }}
            >
              <option value="">（そのまま）</option>
              {sortableColumns.map((c) => (
                <option key={c.key} value={c.key}>
                  {c.label}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={() =>
                setSortOrder((prev) => (prev === "asc" ? "desc" : "asc"))
              }
              style={{
                padding: "4px 8px",
                borderRadius: 4,
                border: "1px solid #9ca3af",
                background: "#f9fafb",
                fontSize: 12,
                cursor: "pointer",
              }}
            >
              {sortOrder === "asc" ? "昇順" : "降順"}
            </button>
          </div>
        </div>

        {sortedItems.length === 0 && !isLoading ? (
          <p style={{ fontSize: 14, color: "#555" }}>
            結果がありません。条件を変えて検索してください。
          </p>
        ) : (
          <div
            style={{
              maxHeight: 600,
              overflow: "auto",
              borderRadius: 4,
              border: "1px solid #e5e7eb",
            }}
          >
            <table
              style={{
                width: "100%",
                borderCollapse: "collapse",
                fontSize: 13,
              }}
            >
              <thead>
                <tr>
                  <th style={thStyle}>ASIN</th>
                  <th style={thStyle}>タイトル</th>
                  <th style={thStyle}>Amazon</th>
                  <th style={thStyle}>楽天</th>
                  <th style={thStyle}>粗利</th>
                  <th style={thStyle}>ROI</th>
                  <th style={thStyle}>チェック日時</th>
                  <th style={thStyle}>Amazonリンク</th>
                  <th style={thStyle}>楽天リンク</th>
                </tr>
              </thead>
              <tbody>
                {sortedItems.map((item) => (
                  <tr key={item.asin} style={{ borderBottom: "1px solid #eee" }}>
                    <td style={tdStyle}>{item.asin}</td>
                    <td style={tdStyle}>{item.title ?? ""}</td>
                    <td style={tdStyle}>{formatYen(item.amazon_price)}</td>
                    <td style={tdStyle}>{formatYen(item.rakuten_price)}</td>
                    <td style={tdStyle}>{formatYen(item.profit_per_item)}</td>
                    <td style={tdStyle}>{formatPercent(item.roi_percent)}</td>
                    <td style={tdStyle}>{item.checked_at}</td>
                    <td style={tdStyle}>
                      {item.amazon_url ? (
                        <a
                          href={item.amazon_url}
                          target="_blank"
                          rel="noreferrer"
                          style={{ color: "#2563eb" }}
                        >
                          開く
                        </a>
                      ) : (
                        ""
                      )}
                    </td>
                    <td style={tdStyle}>
                      {item.rakuten_url ? (
                        <a
                          href={item.rakuten_url}
                          target="_blank"
                          rel="noreferrer"
                          style={{ color: "#2563eb" }}
                        >
                          開く
                        </a>
                      ) : (
                        ""
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
};

const thStyle: React.CSSProperties = {
  position: "sticky",
  top: 0,
  background: "#f3f4f6",
  padding: "6px 8px",
  borderBottom: "1px solid #d1d5db",
  textAlign: "left",
  whiteSpace: "nowrap",
};

const tdStyle: React.CSSProperties = {
  padding: "4px 8px",
  verticalAlign: "top",
  maxWidth: 260,
  wordBreak: "break-all",
};

export default PriceSearchPage;
