// src/components/ForecastChart.js
import React, { useMemo, useState, useCallback, useEffect, useRef } from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ReferenceDot,
} from "recharts";

const fmtCurrency = (n) =>
  typeof n === "number"
    ? n.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 })
    : n;

const pickValue = (p) => {
  const raw =
    p.total ?? p.total_sales ?? p.sales ?? p.value ?? p.amount ?? p.y ?? p.sum ?? p.pred ?? p.predicted ?? 0;
  const num = typeof raw === "string" ? parseFloat(raw) : raw;
  return Number.isFinite(num) ? num : 0;
};

const ClickableDot = ({ cx, cy, payload, onSelect }) => {
  if (typeof cx !== "number" || typeof cy !== "number") return null;
  const handle = (e) => {
    e.stopPropagation();
    const pt = { date: payload.date, value: payload.y, source: payload.source || "history", cx, cy };
    console.log("[Dot] click →", pt);
    onSelect?.(pt);
  };
  return (
    <circle
      cx={cx}
      cy={cy}
      r={5}
      fill="#3182ce"
      stroke="#fff"
      strokeWidth={2}
      style={{ cursor: "pointer" }}
      onClick={handle}
    />
  );
};

const ClickableActiveDot = ({ cx, cy, payload, onSelect }) => {
  if (typeof cx !== "number" || typeof cy !== "number") return null;
  const handle = (e) => {
    e.stopPropagation();
    const pt = { date: payload.date, value: payload.y, source: payload.source || "history", cx, cy };
    console.log("[ActiveDot] click →", pt);
    onSelect?.(pt);
  };
  return (
    <circle
      cx={cx}
      cy={cy}
      r={7}
      fill="#2b6cb0"
      stroke="#fff"
      strokeWidth={2}
      style={{ cursor: "pointer" }}
      onClick={handle}
    />
  );
};

export default function ForecastChart({
  history = [],
  forecast = [],
  height = 360,
  onPointSelect,
  focusPoint,       // { date, value, source, cx, cy }
  focusSummary,
  focusLoading,
  onClosePopup,
}) {
  const wrapRef = useRef(null);

  useEffect(() => {
    console.log("[FC] mounted");
  }, []);

  const data = useMemo(() => {
    const h = (Array.isArray(history) ? history : []).map((p) => ({ ...p, y: pickValue(p), source: "history" }));
    const f = (Array.isArray(forecast) ? forecast : []).map((p) => ({ ...p, y: pickValue(p), source: "forecast" }));
    const combined = [...h, ...f];
    console.log("[FC] normalized points:", combined.length, combined.slice(0, 2));
    return combined;
  }, [history, forecast]);

  const [hoverIdx, setHoverIdx] = useState(null);

  const handleMouseMove = useCallback(
    (e) => {
      if (e?.isTooltipActive && e?.activePayload?.[0]?.payload) {
        const payload = e.activePayload[0].payload;
        const idx =
          data.indexOf(payload) !== -1
            ? data.indexOf(payload)
            : data.findIndex((d) => d.date === payload.date);
        setHoverIdx(idx >= 0 ? idx : null);
      } else {
        setHoverIdx(null);
      }
    },
    [data]
  );

  const handleLineClick = useCallback(
    (d, idx) => {
      if (!onPointSelect || !d) return;
      const pt = { date: d.date, value: d.y, source: d.source || "history" };
      console.log("[Line] click idx=", idx, pt);
      onPointSelect(pt);
    },
    [onPointSelect]
  );

  const handleChartClick = useCallback(
    (e) => {
      if (!onPointSelect) return;

      if (hoverIdx != null && data[hoverIdx]) {
        const p = data[hoverIdx];
        const pt = { date: p.date, value: p.y, source: p.source || "history" };
        console.log("[Chart] click via hoverIdx", hoverIdx, pt);
        onPointSelect(pt);
        return;
      }

      const p = e?.activePayload?.[0]?.payload;
      if (p) {
        const pt = { date: p.date, value: p.y, source: p.source || "history" };
        console.log("[Chart] click via activePayload", pt);
        onPointSelect(pt);
        return;
      }

      const bbox = wrapRef.current?.getBoundingClientRect();
      const cx = e?.chartX, cy = e?.chartY;
      let el = null;
      if (bbox && typeof cx === "number" && typeof cy === "number") {
        el = document.elementFromPoint(Math.round(bbox.left + cx), Math.round(bbox.top + cy));
      }
      console.warn("[Chart] click had no payload. hoverIdx:", hoverIdx, "chartX/Y:", cx, cy, "el:", el);
    },
    [hoverIdx, data, onPointSelect]
  );

  const popup =
    focusPoint && focusPoint.date && typeof focusPoint.value === "number" &&
    typeof focusPoint.cx === "number" && typeof focusPoint.cy === "number"
      ? { x: focusPoint.cx + 8, y: Math.max(0, focusPoint.cy - 80) }
      : null;

  return (
    <div ref={wrapRef} style={{ position: "relative" }}>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart
          data={data}
          onMouseMove={handleMouseMove}
          onClick={handleChartClick}
          style={{ cursor: "pointer" }}
        >
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="date"
            tickFormatter={(d) => {
              try { return new Date(d).toLocaleDateString(undefined, { month: "short", year: "2-digit" }); }
              catch { return d; }
            }}
          />
          <YAxis tickFormatter={(v) => (typeof v === "number" ? v.toLocaleString() : v)} />
          <Tooltip
            formatter={(v, _n, { payload }) => [
              fmtCurrency(v),
              payload?.source === "forecast" ? "Forecast" : "Actual",
            ]}
            labelFormatter={(d) => new Date(d).toLocaleDateString()}
          />

          <Line
            type="monotone"
            dataKey="y"
            stroke="#3182ce"
            strokeWidth={2}
            onClick={handleLineClick}
            dot={(props) => <ClickableDot {...props} onSelect={onPointSelect} />}            // function form
            activeDot={(props) => <ClickableActiveDot {...props} onSelect={onPointSelect} />} // function form
            isAnimationActive={false}
          />

          {focusPoint && focusPoint.date && typeof focusPoint.value === "number" && (
            <ReferenceDot
              x={focusPoint.date}
              y={focusPoint.value}
              r={6}
              fill="#e53e3e"
              stroke="#fff"
              isFront
            />
          )}

          {popup && (
            <foreignObject x={popup.x} y={popup.y} width={260} height={140}>
              <div
                style={{
                  position: "relative",
                  background: "white",
                  border: "1px solid #E2E8F0",
                  borderRadius: 8,
                  boxShadow: "0 6px 16px rgba(0,0,0,0.12)",
                  padding: 10,
                  fontSize: 12,
                  lineHeight: 1.35,
                }}
              >
                <button
                  onClick={(e) => { e.stopPropagation(); onClosePopup?.(); }}
                  style={{
                    position: "absolute", top: 6, right: 8, border: "none",
                    background: "transparent", cursor: "pointer", fontSize: 16, lineHeight: 1,
                  }}
                  aria-label="Close insight"
                  title="Close"
                >
                  ×
                </button>
                <div style={{ fontWeight: 600, marginBottom: 6 }}>
                  {new Date(focusPoint.date).toLocaleDateString()} • {fmtCurrency(focusPoint.value)}
                </div>
                <div style={{ maxHeight: 88, overflow: "auto", whiteSpace: "pre-wrap" }}>
                  {focusLoading ? "Analyzing…" : (focusSummary || "No insight available.")}
                </div>
              </div>
            </foreignObject>
          )}
        </LineChart>
      </ResponsiveContainer>

      {/* HUD */}
      <div
        style={{
          position: "absolute",
          bottom: 6,
          left: 6,
          background: "rgba(0,0,0,0.65)",
          color: "white",
          padding: "6px 8px",
          fontSize: 11,
          borderRadius: 6,
          pointerEvents: "none",
        }}
      >
        <div><b>DEBUG</b> ForecastChart</div>
        <div>points: {data.length}</div>
        <div>hoverIdx: {hoverIdx === null ? "null" : hoverIdx}</div>
        <div>
          focus: {focusPoint && focusPoint.date != null && focusPoint.value != null
            ? `${focusPoint.date} • ${focusPoint.value}`
            : "none"}
        </div>
      </div>
    </div>
  );
}
