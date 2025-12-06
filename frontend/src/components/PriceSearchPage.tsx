// frontend/src/components/PriceSearchPage.tsx
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

  const handleChangeLimitSelect = (
    e: React.ChangeEvent<HTMLSelectElement>
  ): void => {
    const value = e.target.value;
    setCondition((prev) => ({
      ...prev,
      limit: value === "" ? undefined : Number(value),
    }));
  };

  // ====== プリセットボタン（Keepa風） ======
  const applyPreset = (type: "profit1000" | "roi10" | "profit2000roi10") => {
    setCondition((prev) => {
      if (type === "profit1000") {
        return { ...prev, min_profit: 1000 };
      }
      if (type === "roi10") {
        return { ...prev, min_roi: 10 };
      }
      // profit2000roi10
      return { ...prev, min_profit: 2000, min_roi: 10 };
    });
  };

  // ====== 検索実行 ======
  const handleSearch = async () => {
    setIsLoading(true);
    setLoadError(null);
    try {
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
      setSummary(summaryRes ?? null);
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
      // 必要ならここで await handleSearch() で再取得してもOK
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
        minHeight: "100vh",
        padding: "16px 24px 32px",
        maxWidth: 1400,
        margin: "0 auto",
        fontFamily:
          'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
        background: "#f3f4f6",
      }}
    >
      <h1
        style={{
          fontSize: 22,
          fontWeight: 700,
          marginBottom: 12,
          color: "#111827",
        }}
      >
        価格差検索ダッシュボード
      </h1>

      {/* ====== バッチ実行エリア ====== */}
      <section
        style={{
          marginBottom: 16,
          padding: 16,
          borderRadius: 8,
          border: "1px solid #e5e7eb",
          background: "#ffffff",
        }}
      >
        <h2 style={{ fontSize: 16, marginBottom: 6 }}>Keepaバッチ実行</h2>
        <p style={{ marginBottom: 10, fontSize: 13, color: "#6b7280" }}>
          ローカルのバッチ（Keepa検索 → DB登録 → Excel出力）を実行します。
        </p>

        <button
          type="button"
          onClick={handleRunJob}
          disabled={jobLoading}
          style={{
            padding: "6px 16px",
            borderRadius: 999,
            border: "1px solid #2563eb",
            cursor: jobLoading ? "default" : "pointer",
            background: jobLoading ? "#bfdbfe" : "#2563eb",
            color: "#fff",
            fontWeight: 600,
            fontSize: 13,
          }}
        >
          {jobLoading ? "実行中..." : "バッチを実行する"}
        </button>

        {jobError && (
          <div
            style={{
              marginTop: 10,
              padding: 8,
              borderRadius: 6,
              background: "#fef2f2",
              color: "#b91c1c",
              fontSize: 12,
            }}
          >
            {jobError}
          </div>
        )}

        {runningJob && (
          <div
            style={{
              marginTop: 12,
              padding: 10,
              borderRadius: 6,
              background: "#f9fafb",
              fontSize: 13,
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
              gap: 8,
            }}
          >
            <div>
              <div style={{ fontSize: 11, color: "#6b7280" }}>ステータス</div>
              <div style={{ fontWeight: 600 }}>{runningJob.status}</div>
            </div>
            {runningJob.asin_count !== undefined && (
              <div>
                <div style={{ fontSize: 11, color: "#6b7280" }}>
                  ヒット件数
                </div>
                <div style={{ fontWeight: 600 }}>
                  {runningJob.asin_count} 件
                </div>
              </div>
            )}
            {runningJob.excel_path && (
              <div style={{ gridColumn: "1 / -1" }}>
                <div style={{ fontSize: 11, color: "#6b7280" }}>
                  Excel出力先
                </div>
                <code
                  style={{
                    display: "block",
                    marginTop: 4,
                    padding: 6,
                    borderRadius: 4,
                    background: "#111827",
                    color: "#e5e7eb",
                    fontSize: 11,
                    overflowX: "auto",
                  }}
                >
                  {runningJob.excel_path}
                </code>
              </div>
            )}
          </div>
        )}
      </section>

      {/* ====== 検索条件エリア（Keepa風） ====== */}
      <section
        style={{
          marginBottom: 16,
          borderRadius: 8,
          border: "1px solid #d1d5db",
          background: "#f9fafb",
        }}
      >
        {/* 上部のプリセットバー */}
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            alignItems: "center",
            gap: 8,
            padding: "8px 10px",
            borderBottom: "1px solid #e5e7eb",
            background: "#f3f4f6",
          }}
        >
          <button
            type="button"
            style={{
              padding: "4px 10px",
              borderRadius: 4,
              border: "1px solid #9ca3af",
              background: "#e5e7eb",
              fontSize: 12,
              cursor: "default",
            }}
          >
            ▾ フィルタ設定
          </button>
          <button
            type="button"
            onClick={() => applyPreset("profit1000")}
            style={presetButtonStyle}
          >
            利益¥1,000以上
          </button>
          <button
            type="button"
            onClick={() => applyPreset("roi10")}
            style={presetButtonStyle}
          >
            利益率10%以上
          </button>
          <button
            type="button"
            onClick={() => applyPreset("profit2000roi10")}
            style={presetButtonStyle}
          >
            粗利2000円＆利益率10%以上
          </button>

          <div
            style={{
              marginLeft: "auto",
              display: "flex",
              alignItems: "center",
              gap: 8,
              fontSize: 12,
              color: "#4b5563",
            }}
          >
            <span>表示件数</span>
            <select
              value={condition.limit ?? 50}
              onChange={handleChangeLimitSelect}
              style={{
                padding: "2px 6px",
                fontSize: 12,
                borderRadius: 4,
                border: "1px solid #d1d5db",
                background: "#ffffff",
              }}
            >
              <option value={20}>20</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
              <option value={200}>200</option>
            </select>
            <span>
              検索結果:{" "}
              <strong style={{ fontWeight: 600 }}>{items.length}</strong> 件
            </span>
          </div>
        </div>

        {/* 本体フォームエリア */}
        <div
          style={{
            padding: "12px 14px 14px",
            background: "#f9fafb",
          }}
        >
          {/* 1段目：フリーワード */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "120px 1fr",
              columnGap: 10,
              rowGap: 6,
              alignItems: "center",
              marginBottom: 8,
            }}
          >
            <div
              style={{
                fontSize: 12,
                color: "#4b5563",
                textAlign: "right",
                paddingRight: 6,
              }}
            >
              検索:
            </div>
            <input
              type="text"
              value={condition.keyword ?? ""}
              onChange={handleChangeKeyword}
              style={filterInputStyle}
              placeholder="フリーワード（ASIN / タイトル）"
            />
          </div>

          {/* 2段目：粗利・ROI */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "120px 1fr 120px 1fr",
              columnGap: 10,
              rowGap: 6,
              alignItems: "center",
              marginBottom: 8,
            }}
          >
            <div
              style={{
                fontSize: 12,
                color: "#4b5563",
                textAlign: "right",
                paddingRight: 6,
              }}
            >
              利益（円）:
            </div>
            <div>
              <input
                type="number"
                value={condition.min_profit ?? ""}
                onChange={handleChangeNumber("min_profit")}
                style={{
                  ...filterInputStyle,
                  maxWidth: 120,
                  marginRight: 4,
                }}
              />
              <span style={{ fontSize: 12, color: "#6b7280" }}>〜</span>
            </div>

            <div
              style={{
                fontSize: 12,
                color: "#4b5563",
                textAlign: "right",
                paddingRight: 6,
              }}
            >
              利益率（%）:
            </div>
            <div>
              <input
                type="number"
                value={condition.min_roi ?? ""}
                onChange={handleChangeNumber("min_roi")}
                style={{
                  ...filterInputStyle,
                  maxWidth: 120,
                  marginRight: 4,
                }}
              />
              <span style={{ fontSize: 12, color: "#6b7280" }}>〜</span>
            </div>
          </div>

          {/* 3段目：その他 */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "120px 1fr 120px 1fr",
              columnGap: 10,
              rowGap: 6,
              alignItems: "center",
              marginBottom: 10,
            }}
          >
            <div
              style={{
                fontSize: 12,
                color: "#4b5563",
                textAlign: "right",
                paddingRight: 6,
              }}
            >
              最大件数:
            </div>
            <div>
              <input
                type="number"
                value={condition.limit ?? ""}
                onChange={handleChangeNumber("limit")}
                style={{
                  ...filterInputStyle,
                  maxWidth: 100,
                  marginRight: 4,
                }}
              />
            </div>

            <div
              style={{
                fontSize: 12,
                color: "#4b5563",
                textAlign: "right",
                paddingRight: 6,
              }}
            >
              フィルタ:
            </div>
            <div>
              <label
                style={{
                  fontSize: 12,
                  color: "#374151",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 4,
                }}
              >
                <input
                  type="checkbox"
                  checked={condition.only_pass_filter ?? false}
                  onChange={handleChangeOnlyPassFilter}
                />
                pass_filter = true のみ取得
              </label>
            </div>
          </div>

          {/* ボタン行 */}
          <div
            style={{
              display: "flex",
              justifyContent: "flex-end",
              gap: 8,
              marginTop: 4,
            }}
          >
            <button
              type="button"
              onClick={() =>
                setCondition({
                  keyword: "",
                  min_profit: undefined,
                  min_roi: undefined,
                  limit: 50,
                  only_pass_filter: false,
                })
              }
              style={{
                padding: "5px 10px",
                borderRadius: 4,
                border: "1px solid #d1d5db",
                background: "#ffffff",
                fontSize: 12,
                color: "#374151",
                cursor: "pointer",
              }}
            >
              フィルタをクリア
            </button>
            <button
              type="button"
              onClick={handleSearch}
              disabled={isLoading}
              style={{
                padding: "6px 14px",
                borderRadius: 4,
                border: "1px solid #2563eb",
                background: isLoading ? "#bfdbfe" : "#2563eb",
                color: "#fff",
                cursor: isLoading ? "default" : "pointer",
                fontSize: 13,
                fontWeight: 600,
              }}
            >
              {isLoading ? "検索中..." : "フィルタを適用"}
            </button>
          </div>

          {loadError && (
            <div
              style={{
                marginTop: 8,
                padding: 8,
                borderRadius: 6,
                background: "#fef2f2",
                color: "#b91c1c",
                fontSize: 12,
              }}
            >
              {loadError}
            </div>
          )}

          {summary && (
            <div
              style={{
                marginTop: 8,
                padding: 8,
                borderRadius: 6,
                background: "#eef2ff",
                fontSize: 12,
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
                gap: 8,
              }}
            >
              <div>
                <div style={{ color: "#4b5563" }}>最新チェック</div>
                <div style={{ fontWeight: 600 }}>
                  {summary.latest_checked_at ?? "-"}
                </div>
              </div>
              <div>
                <div style={{ color: "#4b5563" }}>件数</div>
                <div style={{ fontWeight: 600 }}>{summary.count}</div>
              </div>
              <div>
                <div style={{ color: "#4b5563" }}>平均粗利</div>
                <div style={{ fontWeight: 600 }}>
                  {formatYen(summary.avg_profit)}
                </div>
              </div>
              <div>
                <div style={{ color: "#4b5563" }}>平均ROI</div>
                <div style={{ fontWeight: 600 }}>
                  {formatPercent(summary.avg_roi)}
                </div>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* ====== 一覧表示エリア ====== */}
      <section
        style={{
          padding: 12,
          borderRadius: 8,
          border: "1px solid #d1d5db",
          background: "#ffffff",
        }}
      >
        <div
          style={{
            marginBottom: 8,
            display: "flex",
            flexWrap: "wrap",
            gap: 8,
            alignItems: "center",
          }}
        >
          <h2 style={{ fontSize: 15, margin: 0, color: "#111827" }}>
            検索結果一覧
          </h2>

          <div
            style={{
              marginLeft: "auto",
              display: "flex",
              gap: 8,
              alignItems: "center",
              fontSize: 12,
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
              style={{
                padding: "2px 6px",
                fontSize: 12,
                borderRadius: 4,
                border: "1px solid #d1d5db",
                background: "#ffffff",
              }}
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
                padding: "3px 8px",
                borderRadius: 999,
                border: "1px solid #9ca3af",
                background: "#f9fafb",
                fontSize: 11,
                cursor: "pointer",
              }}
            >
              {sortOrder === "asc" ? "昇順" : "降順"}
            </button>
          </div>
        </div>

        {sortedItems.length === 0 && !isLoading ? (
          <p style={{ fontSize: 13, color: "#6b7280", padding: "4px 2px" }}>
            検索条件を指定してください。
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
                fontSize: 12,
                background: "#ffffff",
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
                {sortedItems.map((item, index) => (
                  <tr
                    key={item.asin}
                    style={{
                      borderBottom: "1px solid #f3f4f6",
                      background: index % 2 === 0 ? "#ffffff" : "#f9fafb",
                    }}
                  >
                    <td style={tdStyle}>{item.asin}</td>
                    <td style={tdStyle}>{item.title ?? ""}</td>
                    <td
                      style={{
                        ...tdStyle,
                        textAlign: "right",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {formatYen(item.amazon_price)}
                    </td>
                    <td
                      style={{
                        ...tdStyle,
                        textAlign: "right",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {formatYen(item.rakuten_price)}
                    </td>
                    {/* ★ 粗利はバックエンドの profit_per_item をそのまま表示 */}
                    <td
                      style={{
                        ...tdStyle,
                        textAlign: "right",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {formatYen(item.profit_per_item)}
                    </td>
                    <td
                      style={{
                        ...tdStyle,
                        textAlign: "right",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {formatPercent(item.roi_percent)}
                    </td>
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

const presetButtonStyle: React.CSSProperties = {
  padding: "4px 10px",
  borderRadius: 4,
  border: "1px solid #d1d5db",
  background: "#ffffff",
  fontSize: 12,
  cursor: "pointer",
  color: "#374151",
};

const filterInputStyle: React.CSSProperties = {
  width: "100%",
  padding: "4px 6px",
  fontSize: 12,
  borderRadius: 4,
  border: "1px solid #d1d5db",
  background: "#ffffff",
  color: "#111827",
  outline: "none",
  boxSizing: "border-box",
};

const thStyle: React.CSSProperties = {
  position: "sticky",
  top: 0,
  zIndex: 1,
  background: "#f3f4f6",
  padding: "6px 8px",
  borderBottom: "1px solid #e5e7eb",
  textAlign: "left",
  whiteSpace: "nowrap",
  fontSize: 11,
  color: "#4b5563",
  fontWeight: 600,
};

const tdStyle: React.CSSProperties = {
  padding: "5px 8px",
  verticalAlign: "top",
  maxWidth: 260,
  wordBreak: "break-all",
  color: "#111827",
  fontSize: 12,
};

export default PriceSearchPage;
