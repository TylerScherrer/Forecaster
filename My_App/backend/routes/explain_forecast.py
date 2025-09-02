# backend/routes/explain_forecast.py
from __future__ import annotations

from flask import Blueprint, request, jsonify, current_app
from typing import List, Dict, Any, Tuple, Optional
import os
import requests
from datetime import datetime

explain_bp = Blueprint("explain_forecast", __name__)

# --------- Model config ----------
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL   = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")


# --------- helpers ----------
def _extract_timeline(data: Any) -> List[Dict[str, Any]]:
    if isinstance(data, list):
        timeline = data
    elif isinstance(data, dict) and "timeline" in data:
        timeline = data["timeline"]
    else:
        raise ValueError("Expected a list or an object with a 'timeline' key.")
    if not isinstance(timeline, list) or not timeline:
        raise ValueError("Timeline must be a non-empty list.")
    return timeline

def _pick_value(entry: Dict[str, Any]) -> Optional[float]:
    for k in ("total", "total_sales", "sales", "value", "amount", "y", "sum", "pred", "predicted"):
        if k in entry:
            try:
                return float(entry[k])
            except (TypeError, ValueError):
                return None
    return None

def _norm_points(timeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    pts = []
    for t in timeline:
        d = str(t.get("date") or "")[:10]
        v = _pick_value(t)
        if not d or v is None:
            continue
        pts.append({"date": d, "value": float(v), "source": t.get("source", "history")})
    pts.sort(key=lambda x: x["date"])
    return pts

def _pairs(pts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for i in range(1, len(pts)):
        a, b = pts[i-1], pts[i]
        dv = b["value"] - a["value"]
        pct = (dv / a["value"] * 100.0) if a["value"] else None
        out.append({
            "from_date": a["date"], "to_date": b["date"],
            "from_value": a["value"], "to_value": b["value"],
            "to_source": b["source"], "dv": dv, "pct": pct
        })
    return out

def _find_index_by_date(pts: List[Dict[str, Any]], date_str: str) -> int:
    for i, p in enumerate(pts):
        if p["date"][:10] == str(date_str)[:10]:
            return i
    return -1

def _render_focus_facts(pts: List[Dict[str, Any]], idx: int) -> str:
    left2  = pts[idx-2] if idx-2 >= 0 else None
    left1  = pts[idx-1] if idx-1 >= 0 else None
    mid    = pts[idx]
    right1 = pts[idx+1] if idx+1 < len(pts) else None

    def line(p):
        return f"{p['date']},{p['value']:.2f},{p['source']}"
    lines = ["date,value,source"]
    for p in (left2, left1, mid, right1):
        if p:
            lines.append(line(p))

    # deltas vs previous months
    deltas = []
    if left1:
        dv = mid["value"] - left1["value"]
        pct = (dv / left1["value"] * 100.0) if left1["value"] else None
        pct_str = "NA" if pct is None else f"{pct:.2f}"
        deltas.append(f"prev_vs_focus: {left1['date']} → {mid['date']}, dv:{dv:.2f}, pct:{pct_str}")
    if left2 and left1:
        dv = mid["value"] - left2["value"]
        pct = (dv / left2["value"] * 100.0) if left2["value"] else None
        pct_str = "NA" if pct is None else f"{pct:.2f}"
        deltas.append(f"prev2_vs_focus: {left2['date']} → {mid['date']}, dv:{dv:.2f}, pct:{pct_str}")
    if right1:
        dv = right1["value"] - mid["value"]
        pct = (dv / mid["value"] * 100.0) if mid["value"] else None
        pct_str = "NA" if pct is None else f"{pct:.2f}"
        deltas.append(f"focus_vs_next: {mid['date']} → {right1['date']}, dv:{dv:.2f}, pct:{pct_str}")

    return "FOCUS_ROWS (CSV):\n" + "\n".join(lines) + ("\n" + "\n".join(deltas) if deltas else "")


def _render_global_facts(pts: List[Dict[str, Any]]) -> str:
    pr = _pairs(pts)
    rows = ["PAIRS (from,to,from_val,to_val,dv,pct,to_source)"]
    for r in pr:
        pct_str = "NA" if r["pct"] is None else f"{r['pct']:.2f}"
        rows.append(
            f"{r['from_date']},{r['to_date']},"
            f"{r['from_value']:.2f},{r['to_value']:.2f},"
            f"{r['dv']:.2f},{pct_str},{r['to_source']}"
        )
    return "\n".join(rows)


def _build_prompt_total(timeline: List[Dict[str, Any]], focus: Optional[Dict[str, Any]]) -> str:
    pts = _norm_points(timeline)
    if not pts:
        raise ValueError("No usable timeline points.")

    # keep a compact, recent window to reduce drift
    pts = pts[-18:]

    # ---------- FOCUS MODE ----------
    if focus and focus.get("date"):
        idx = _find_index_by_date(pts, str(focus["date"]))
        if idx == -1:
            idx = len(pts) - 1  # fallback to most recent if not found
        ff = _render_focus_facts(pts, idx)
        mid = pts[idx]  # the actual row we consider "focus"

        return f"""You are a careful retail analyst.

FOCUS_DATE: {mid['date']}
FOCUS_SOURCE: {mid['source']}

{ff}

STRICT RULES:
- Treat each change as (to_value - from_value) for the exact dates shown. Do not shift or infer months.
- Only discuss the FOCUS_DATE month; do NOT summarize other months.
- If FOCUS_SOURCE == "forecast", append " (forecast)" after that month's name when you mention it.

TASK:
- Write exactly 3 bullets about the FOCUS month only, quantifying changes vs the previous month (and previous-2 if present) using the dv/pct already listed in FOCUS_ROWS.
- Add one bullet comparing the focus value to the local 3–4 month neighborhood shown in FOCUS_ROWS (high/low/outlier).
- Finish with **Next actions:** and exactly 2 short, data-specific actions tied to the focus month.
- Markdown bullets only; no preamble.
"""

    # ---------- GLOBAL MODE ----------
    gf = _render_global_facts(pts)
    return f"""You are a precise retail analyst.

{gf}

STRICT RULES:
- Each change refers to the PAIR 'from_date → to_date' and its dv/pct exactly as listed; do not realign or offset months.
- If a pair's to_source == "forecast", append "(forecast)" after the TO month when referenced.

TASK:
- In 3–5 bullets, summarize the key month-to-month changes using the PAIRS.
- Name the single largest rise and the single largest drop.
- Finish with **Next actions:** and exactly 2 data-specific actions.
- Markdown bullets only; no preamble.
"""


def _call_groq(prompt: str, timeout: int = 20) -> Tuple[str, int]:
    api_key = os.environ.get("GROQ_API_KEY") or current_app.config.get("GROQ_API_KEY")
    if not api_key:
        return ("GROQ_API_KEY is not set.", 498)
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": "You are a precise retail analyst. Be numeric and concrete."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 700,
    }
    try:
        r = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=timeout)
    except requests.Timeout:
        return ("The explanation service timed out. Please try again.", 504)
    except requests.RequestException as e:
        return (f"Network error calling Groq: {e}", 502)
    if r.status_code != 200:
        return (f"Groq API error ({r.status_code}): {r.text}", r.status_code)
    try:
        return (r.json()["choices"][0]["message"]["content"], 200)
    except Exception:
        return ("Groq API returned an unexpected response format.", 502)


@explain_bp.route("/api/explain_forecast", methods=["POST"])
def explain_forecast():
    try:
        data = request.get_json(silent=True)
        timeline = _extract_timeline(data)
        focus = None
        if isinstance(data, dict) and isinstance(data.get("focus"), dict):
            f = data["focus"]
            focus = {k: f.get(k) for k in ("date", "value", "source")}
        prompt = _build_prompt_total(timeline, focus=focus)
        text, status = _call_groq(prompt)
        if status != 200:
            current_app.logger.error("Groq call failed: %s", text)
            return jsonify({"summary": "* Unable to generate insight at the moment."}), 200
        return jsonify({"summary": (text or "").strip()}), 200
    except ValueError as ve:
        current_app.logger.warning("Bad request to /api/explain_forecast: %s", ve)
        return jsonify({"error": str(ve)}), 400
    except Exception:
        current_app.logger.exception("Unexpected error in /api/explain_forecast")
        return jsonify({"error": "Failed to generate explanation"}), 500
