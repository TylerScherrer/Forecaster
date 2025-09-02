// src/sections/SalesGrowthCard.jsx (or wherever you render <ForecastChart/>)
import React, { useMemo, useState } from "react";
import ForecastChart from "../components/ForecastChart";

const API_BASE = process.env.REACT_APP_API_BASE || ""; // same-origin backend

export default function SalesGrowthCard({ history = [], forecast = [] }) {
  const [focusPoint, setFocusPoint] = useState(null);
  const [focusLoading, setFocusLoading] = useState(false);
  const [focusSummary, setFocusSummary] = useState("");

  // This is exactly what we POST to the backend. The backend normalizes keys.
  const timeline = useMemo(() => {
    const h = history.map((p) => ({ ...p, source: p.source || "history" }));
    const f = forecast.map((p) => ({ ...p, source: p.source || "forecast" }));
    return [...h, ...f];
  }, [history, forecast]);

  // <- Put the function here (the parent of <ForecastChart/>)
  async function explainPoint(pt) {
    setFocusPoint(pt);        // keep for popup position
    setFocusLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/explain_forecast`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          view: "total",
          timeline,                 // same data you used to draw the chart
          focus: {                  // IMPORTANT: the clicked point
            date: pt.date,
            value: pt.value,
            source: pt.source,      // "forecast" for forecast points
          },
        }),
      });
      const json = await res.json();
      setFocusSummary(json.summary || "No insight available.");
    } catch (e) {
      setFocusSummary("No insight available.");
    } finally {
      setFocusLoading(false);
    }
  }

  return (
    <ForecastChart
      history={history}
      forecast={forecast}
      onPointSelect={explainPoint}           // <- wire it here
      focusPoint={focusPoint}
      focusSummary={focusSummary}
      focusLoading={focusLoading}
      onClosePopup={() => { setFocusPoint(null); setFocusSummary(""); }}
    />
  );
}
