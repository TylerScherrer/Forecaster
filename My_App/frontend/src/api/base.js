// Picks the base URL from env (CRA) or falls back to SWA proxy (/api)
export const API_BASE =
  (process.env.REACT_APP_API_BASE || "").replace(/\/+$/, "") || "/api";

// Build a full URL safely
export const apiUrl = (path) =>
  `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;

// GET as JSON with decent errors
export async function getJSON(path, init = {}) {
  const res = await fetch(apiUrl(path), {
    headers: { Accept: "application/json", ...(init.headers || {}) },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`GET ${path} → ${res.status} ${res.statusText} ${text}`);
  }
  return res.json();
}

// POST JSON convenience
export async function postJSON(path, body, init = {}) {
  return getJSON(path, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(init.headers || {}) },
    body: JSON.stringify(body),
    ...init,
  });
}
