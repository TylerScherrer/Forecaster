// src/api/forecastService.js
import { API_BASE } from "./base";

/**
 * GET /api/forecast/:store_id
 * Returns: { history: [...], forecast: [...] | {...} }
 */
export async function fetchForecast(storeId) {
  const res = await fetch(`${API_BASE}/api/forecast/${storeId}`);
  if (!res.ok) throw new Error(`forecast ${res.status}`);
  return res.json();
}

/**
 * POST /api/explain_forecast
 * Safely normalizes and guards against empty timelines.
 * rawTimeline: [{ date, value|total|sales, source? }, ...]
 * focus (optional): { date, value, source }
 */
export async function explainForecast(rawTimeline, focus) {
  // normalize input and DROP bad rows
  const timeline = (Array.isArray(rawTimeline) ? rawTimeline : [])
    .map(p => ({
      date: (p.date || "").slice(0, 10),
      value: Number(p.value ?? p.total ?? p.sales ?? 0),
      source: p.source || "actual",
    }))
    .filter(p => p.date && Number.isFinite(p.value));

  // Avoid calling backend with an empty list
  if (timeline.length === 0) return { summary: "" };

  const body = focus ? { view: "total", timeline, focus } : { view: "total", timeline };

  const res = await fetch(`${API_BASE}/api/explain_forecast`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    // keep UI stable on 4xx/5xx
    try { return await res.json(); } catch { return { summary: "" }; }
  }
  return res.json();
}
