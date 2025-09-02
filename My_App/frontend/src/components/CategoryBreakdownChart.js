// src/components/CategoryBreakdownChart.js
import React, { useMemo } from "react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  LabelList,
} from "recharts";

const fmtUSD = (n) =>
  typeof n === "number"
    ? n.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 })
    : n;

// Make labels readable: "AMERICAN_CORDIALS_LIQUEURS" -> "American Cordials & Liqueurs"
function tidyLabel(raw = "") {
  const s = String(raw)
    .replace(/_/g, " ")
    .replace(/\s+&\s+/g, " & ")
    .toLowerCase()
    .replace(/\b\w/g, (m) => m.toUpperCase());
  // Trim long labels so axis stays clean
  return s.length > 26 ? s.slice(0, 23) + "…" : s;
}

export default function CategoryBreakdownChart({
  history = [],
  height = 360,
  topN = 12,
}) {
  // Build dataset from the latest month that actually has a categories object
  const { latestLabel, data } = useMemo(() => {
    const rows = Array.isArray(history) ? [...history] : [];
    rows.sort((a, b) => String(a.date).localeCompare(String(b.date)));

    // Find latest row with categories
    let latest = null;
    for (let i = rows.length - 1; i >= 0; i--) {
      if (rows[i]?.categories && Object.keys(rows[i].categories).length) {
        latest = rows[i];
        break;
      }
    }
    if (!latest) return { latestLabel: "", data: [] };

    const entries = Object.entries(latest.categories || {})
      .map(([name, val]) => ({
        name,
        label: tidyLabel(name),
        value: Number(val) || 0,
      }))
      .filter((d) => Number.isFinite(d.value));

    // Sort desc and keep Top N + Other
    entries.sort((a, b) => b.value - a.value);
    const top = entries.slice(0, Math.max(1, topN));
    const rest = entries.slice(Math.max(1, topN));
    if (rest.length) {
      const otherSum = rest.reduce((s, r) => s + (r.value || 0), 0);
      top.push({ name: "__OTHER__", label: "Other", value: otherSum });
    }

    const label =
      new Date(latest.date).toLocaleDateString(undefined, {
        month: "short",
        year: "numeric",
      }) || String(latest.date);

    return { latestLabel: label, data: top };
  }, [history, topN]);

  if (!data.length) {
    return (
      <div
        style={{
          height,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "#475569",
          border: "1px solid #E2E8F0",
          borderRadius: 12,
          background: "white",
        }}
      >
        No category data available for the latest month.
      </div>
    );
  }

  return (
    <div
      style={{
        height,
        border: "1px solid #E2E8F0",
        borderRadius: 12,
        background: "white",
        padding: 8,
      }}
    >
      <div
        style={{
          fontWeight: 600,
          fontSize: 14,
          margin: "6px 10px 2px",
          color: "#334155",
        }}
      >
        Category Breakdown • {latestLabel}
      </div>
      <ResponsiveContainer width="100%" height={height - 40}>
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 8, right: 16, bottom: 8, left: 120 }}
        >
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            type="number"
            tickFormatter={(v) =>
              typeof v === "number" ? v.toLocaleString() : v
            }
          />
          <YAxis
            type="category"
            dataKey="label"
            width={120}
            tick={{ fontSize: 12 }}
          />
          <Tooltip
            formatter={(v, _n, _payload) => [fmtUSD(v), "Sales"]}
            cursor={{ fill: "rgba(148, 163, 184, 0.12)" }}
          />
          <Bar dataKey="value" fill="#3182ce" radius={[4, 4, 4, 4]}>
            <LabelList
              dataKey="value"
              position="right"
              formatter={(v) =>
                typeof v === "number" ? v.toLocaleString() : v
              }
              style={{ fontSize: 12, fill: "#1e293b" }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
