from __future__ import annotations

from flask import Blueprint, request, jsonify, current_app
from typing import List, Dict, Any, Tuple
import os
import requests

explain_bp = Blueprint("explain_forecast", __name__)

# ----------------------------
# Helpers
# ----------------------------

# ----------------------------
# Safely extract the timeline array from either supported input shape.
# Input:
#   - data (Any): JSON body from POST (either a list of records OR { "timeline": [...] })
#
# Returns:
#   - List[Dict[str, Any]]: The extracted timeline list
#
# Details:
#   1. If body is a list, treat it as the timeline.
#   2. If body is a dict with "timeline", use that.
#   3. Otherwise, raise a ValueError with a descriptive message.
# ----------------------------
def _extract_timeline(data: Any) -> List[Dict[str, Any]]:
    if isinstance(data, list):
        timeline = data
    elif isinstance(data, dict) and "timeline" in data:
        timeline = data["timeline"]
    else:
        raise ValueError("Expected a list or an object with a 'timeline' key.")
    if not isinstance(timeline, list) or len(timeline) < 1:
        raise ValueError("Timeline must be a non-empty list.")
    return timeline



# ---- NEW helpers ------------------------------------------------------------

def _pick_sales_value(entry: Dict[str, Any]) -> float | None:
    """Return a numeric sales value from many possible keys; None if not found."""
    for k in ("total", "total_sales", "sales", "value", "amount", "y", "sum", "pred", "predicted"):
        if k in entry:
            v = entry[k]
            try:
                return float(v)
            except (TypeError, ValueError):
                return None
    return None

def _fmt_usd(n: float) -> str:
    return f"${n:,.0f}"  # whole dollars is fine for UI



# ----------------------------
# Build a friendly, concise prompt for the LLM from a slice of the timeline.
# Input:
#   - timeline (List[Dict]): The full timeline
#   - last_n (int): How many final points to include (default: 4)
#
# Returns:
#   - str: Prompt text ready to send to the LLM
#
# Details:
#   1. Grab the last N entries from the timeline.
#   2. Detect whether entries use 'sales' or 'total_sales'.
#   3. Format lines like "YYYY-MM-DD: $1234.56".
#   4. Compose an instruction for a store manager audience.
# ----------------------------
# ---- UPDATED: build prompt (now accepts focus) ------------------------------

def _build_prompt(
    timeline: List[Dict[str, Any]],
    last_n: int = 4,
    focus: Dict[str, Any] | None = None,
) -> str:
    """Build a short, manager-friendly prompt from the timeline.
       If `focus` is provided, center the window around that point."""
    if not isinstance(timeline, list) or not timeline:
        raise ValueError("Timeline must be a non-empty list.")

    # Defensive: sort by date (string ISO works lexicographically)
    tl = [t for t in timeline if isinstance(t, dict) and "date" in t]
    tl.sort(key=lambda x: x["date"])

    # Decide which slice to use
    if focus and "date" in focus:
        # center a small window around the focused date (2 before, 1 after)
        idx = next((i for i, r in enumerate(tl) if r.get("date") == focus["date"]), None)
        if idx is None:
            window = tl[-last_n:]
        else:
            start = max(0, idx - 2)
            end = min(len(tl), idx + 2)  # exclusive
            window = tl[start:end]
    else:
        window = tl[-last_n:]

    lines: List[str] = []
    for entry in window:
        val = _pick_sales_value(entry)
        if val is None:
            continue
        src = entry.get("source")  # 'history' or 'forecast' if provided by FE
        tag = "forecast" if src == "forecast" else "actual"
        lines.append(f"{entry['date']}: {_fmt_usd(val)} ({tag})")

    if not lines:
        raise ValueError("No usable numeric values found in the timeline.")

    focus_txt = ""
    if focus and "date" in focus and "value" in focus:
        f_src = focus.get("source", "actual")
        focus_txt = (
            f"\nFocus on what changed around {focus['date']} "
            f"({f_src}: {_fmt_usd(float(focus['value']))})."
        )

    return (
        "You are a helpful retail analyst. A store manager needs a simple explanation.\n"
        "Use plain language, 2–3 short bullet points max. Be concrete and actionable.\n\n"
        "Recent points (date: value):\n"
        + "\n".join(lines)
        + focus_txt
    )
# ----------------------------
# Call Groq's Chat Completions API with robust error handling.
# ----------------------------
def _call_groq(prompt: str, model: str = "llama3-8b-8192", timeout: int = 20) -> Tuple[str, int]:
    api_key = os.environ.get("GROQ_API_KEY") or current_app.config.get("GROQ_API_KEY")
    if not api_key:
        return ("GROQ_API_KEY is not set.", 498)  # custom-ish signal used above

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a helpful retail analyst."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
        "max_tokens": 300,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=timeout,
        )
    except requests.Timeout:
        return ("The explanation service timed out. Please try again.", 504)
    except requests.RequestException as re:
        return (f"Network error calling Groq: {re}", 502)

    if resp.status_code != 200:
        return (f"Groq API error ({resp.status_code}): {resp.text}", resp.status_code)

    try:
        content = resp.json()["choices"][0]["message"]["content"]
    except Exception:
        return ("Groq API returned an unexpected response format.", 502)

    return (content, 200)

# ---- UPDATED: route (now parses `focus` and passes it) ----------------------

@explain_bp.route("/api/explain_forecast", methods=["POST"])
def explain_forecast():
    try:
        data = request.get_json(silent=True)
        current_app.logger.debug("Raw incoming data type: %s", type(data))

        timeline = _extract_timeline(data)
        current_app.logger.debug("Timeline len: %s", len(timeline))

        # NEW: accept optional focus hint from frontend
        focus = None
        if isinstance(data, dict):
            f = data.get("focus")
            if isinstance(f, dict):
                focus = {k: f.get(k) for k in ("date", "value", "source")}

        prompt = _build_prompt(timeline, last_n=4, focus=focus)

        text, status = _call_groq(prompt)
        if status != 200:
            current_app.logger.error("Groq call failed: %s", text)
            if status == 498:
                return jsonify({"error": "Server is missing GROQ_API_KEY"}), 500
            return jsonify({"error": "Groq model request failed"}), 502

        explanation = (text or "").strip()
        current_app.logger.info("AI Explanation generated (%d chars)", len(explanation))
        return jsonify({"summary": explanation}), 200

    except ValueError as ve:
        current_app.logger.warning("Bad request to /api/explain_forecast: %s", ve)
        return jsonify({"error": str(ve)}), 400
    except Exception:
        current_app.logger.exception("Unexpected error in /api/explain_forecast")
        return jsonify({"error": "Failed to generate explanation"}), 500