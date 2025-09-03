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
    ? n.toLocaleString(undefined, {
        style: "currency",
        currency: "USD",
        maximumFractionDigits: 0,
      })
    : n;
// --- Popup formatting & placement helpers ---
const CARD_W = 420;
const CARD_MAX_H = 260;

const splitSections = (text) => {
  const pieces = String(text || "").trim().split(/\n\s*\*\*?Next actions?:\*\*?\s*/i);
  return { body: pieces[0] || "", actions: pieces[1] || "" };
};

const parseBullets = (s) =>
  String(s || "")
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean)
    .map((l) => l.replace(/^[*•-]\s+/, "")); // strip bullet markers

const renderInline = (s) => {
  // Preserve **bold** from the model
  const parts = String(s || "").split(/\*\*(.*?)\*\*/g);
  return parts.map((p, i) => (i % 2 ? <strong key={i}>{p}</strong> : <span key={i}>{p}</span>));
};

const getPopupPos = (wrapEl, pt) => {
  const w = wrapEl?.clientWidth || 0;
  let x = (pt.cx ?? 0) + 12;
  if (w && x + CARD_W > w) x = Math.max(0, (pt.cx ?? 0) - CARD_W - 12);

  let y = (pt.cy ?? 0) - CARD_MAX_H - 12;
  if (y < 0) y = (pt.cy ?? 0) + 12;
  return { x, y };
};

// Safe month label from an ISO date string without using Date() (avoids TZ surprises)
const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const makeLabel = (iso) => {
  const m = /(\d{4})-(\d{2})/.exec(String(iso || ""));
  if (!m) return String(iso || "");
  const year = m[1] || "";
  const monIdx = Math.max(0, Math.min(11, parseInt(m[2], 10) - 1));
  return `${MONTHS[monIdx]} ${year.slice(2)}`;
};

const pickValue = (p) => {
  const raw =
    p.total ??
    p.total_sales ??
    p.sales ??
    p.value ??
    p.amount ??
    p.y ??
    p.sum ??
    p.pred ??
    p.predicted ??
    0;
  const num = typeof raw === "string" ? parseFloat(raw) : raw;
  return Number.isFinite(num) ? num : 0;
};

const ClickableDot = ({ cx, cy, payload, onSelect }) => {
  if (typeof cx !== "number" || typeof cy !== "number") return null;
  const handle = (e) => {
    e.stopPropagation();
    const pt = {
      date: payload.date,
      label: payload.label,
      value: payload.y,
      source: payload.source || "history",
      cx,
      cy,
    };
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
    const pt = {
      date: payload.date,
      label: payload.label,
      value: payload.y,
      source: payload.source || "history",
      cx,
      cy,
    };
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
  focusPoint, // { date, label, value, source, cx, cy }
  focusSummary,
  focusLoading,
  onClosePopup,
}) {
  const wrapRef = useRef(null);

  useEffect(() => {
    // mount log
  }, []);

  const data = useMemo(() => {
    const norm = (arr, src) =>
      (Array.isArray(arr) ? arr : []).map((p) => ({
        ...p,
        y: pickValue(p),
        source: p.source || src || "history",
        // prefer backend label; fallback to ISO -> "Mon YY"
        label: p.label || makeLabel(p.date),
      }));
    const h = norm(history, "history");
    const f = norm(forecast, "forecast");
    return [...h, ...f];
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



  const handleChartClick = useCallback(
    (e) => {
      if (!onPointSelect) return;

      if (hoverIdx != null && data[hoverIdx]) {
        const p = data[hoverIdx];
        const pt = { date: p.date, label: p.label, value: p.y, source: p.source || "history" };
        onPointSelect(pt);
        return;
      }

      const p = e?.activePayload?.[0]?.payload;
      if (p) {
        const pt = { date: p.date, label: p.label, value: p.y, source: p.source || "history" };
        onPointSelect(pt);
        return;
      }

      // If we get here, no active payload—nothing to select.
    },
    [hoverIdx, data, onPointSelect]
  );

// Compute popup position (only if we have a valid focus point)
const popup =
  focusPoint &&
  focusPoint.label &&
  typeof focusPoint.value === "number" &&
  typeof focusPoint.cx === "number" &&
  typeof focusPoint.cy === "number"
    ? getPopupPos(wrapRef.current, focusPoint)
    : null;


  return (
    <div ref={wrapRef} style={{ position: "relative" }}>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} onMouseMove={handleMouseMove} onClick={handleChartClick} style={{ cursor: "pointer" }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          {/* X-axis now uses the backend-provided (or derived) label directly */}
          <XAxis dataKey="label" />
          <YAxis tickFormatter={(v) => (typeof v === "number" ? v.toLocaleString() : v)} />
          <Tooltip
            formatter={(v, _n, { payload }) => [
              fmtCurrency(v),
              payload?.source === "forecast" ? "Forecast" : "Actual",
            ]}
            labelFormatter={(_label, payload) => {
              const p = payload?.[0]?.payload;
              return p?.label || p?.date || "";
            }}
          />

          <Line
            type="monotone"
            dataKey="y"
            stroke="#3182ce"
            strokeWidth={2}
            dot={(props) => <ClickableDot {...props} onSelect={onPointSelect} />}
            activeDot={(props) => <ClickableActiveDot {...props} onSelect={onPointSelect} />}
            isAnimationActive={false}
          />


          {/* ReferenceDot must use the same x domain as XAxis (label) */}
          {focusPoint && focusPoint.label && typeof focusPoint.value === "number" && (
            <ReferenceDot x={focusPoint.label} y={focusPoint.value} r={6} fill="#e53e3e" stroke="#fff" isFront />
          )}

         {popup && (
  <foreignObject x={popup.x} y={popup.y} width={CARD_W} height={CARD_MAX_H}>
    <div
      style={{
        position: "relative",
        background: "white",
        border: "1px solid #E2E8F0",
        borderRadius: 12,
        boxShadow: "0 8px 22px rgba(0,0,0,0.16)",
        padding: 14,
        fontSize: 13,
        lineHeight: 1.45,
        maxHeight: CARD_MAX_H,
        overflow: "auto",
      }}
      onClick={(e) => e.stopPropagation()}
    >
      <button
        onClick={(e) => {
          e.stopPropagation();
          onClosePopup?.();
        }}
        style={{
          position: "absolute",
          top: 8,
          right: 10,
          border: "none",
          background: "transparent",
          cursor: "pointer",
          fontSize: 18,
          lineHeight: 1,
        }}
        aria-label="Close insight"
        title="Close"
      >
        ×
      </button>

      {/* Header */}
      <div style={{ fontWeight: 700, marginBottom: 6, fontSize: 14 }}>
        {focusPoint.label} • {fmtCurrency(focusPoint.value)}
        {focusPoint.source === "forecast" ? " (forecast)" : ""}
      </div>

      {/* Render cleaned bullets */}
      <div>
        {(() => {
          const { body, actions } = splitSections(focusSummary);
          const bodyBullets = parseBullets(body);
          const actionBullets = parseBullets(actions);

          return (
            <>
              {bodyBullets.length > 0 ? (
                <ul style={{ margin: "6px 0 0 16px", padding: 0 }}>
                  {bodyBullets.map((l, i) => (
                    <li key={i} style={{ marginBottom: 4 }}>{renderInline(l)}</li>
                  ))}
                </ul>
              ) : (
                <div style={{ color: "#4A5568" }}>
                  {focusLoading ? "Analyzing…" : focusSummary || "No insight available."}
                </div>
              )}

              {actionBullets.length > 0 && (
                <>
                  <div style={{ marginTop: 10, fontWeight: 700 }}>Next actions</div>
                  <ul style={{ margin: "6px 0 0 16px", padding: 0 }}>
                    {actionBullets.map((l, i) => (
                      <li key={i} style={{ marginBottom: 4 }}>{renderInline(l)}</li>
                    ))}
                  </ul>
                </>
              )}
            </>
          );
        })()}
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
          focus: {focusPoint && focusPoint.label != null && focusPoint.value != null
            ? `${focusPoint.label} • ${focusPoint.value}`
            : "none"}
        </div>
      </div>
    </div>
  );
}
