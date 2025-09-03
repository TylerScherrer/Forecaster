from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request
from typing import List, Dict, Tuple
import logging
import time
import re
import pandas as pd

from .data_access import (
    _ensure_required_objects,
    _predict_preview,  # per-row fallback when model is usable
)

store_bp = Blueprint("store", __name__)

# In-memory cache (keeps first load fast across refreshes)
_STORES_CACHE: Dict[Tuple, Tuple[float, List[Dict]]] = {}
_CACHE_TTL_SEC = 600  # bump to 300 if you want

# ----------------------------- normalization ------------------------------

def _norm_name(name: str) -> str:
    return re.sub(r'[^a-z0-9]+', '', str(name).lower())

def _guess_col(df: pd.DataFrame, aliases: List[str]) -> str | None:
    wanted = {_norm_name(a) for a in aliases}
    # direct match on normalized names
    for col in df.columns:
        if _norm_name(col) in wanted:
            return col
    # fuzzy contains fallback
    for col in df.columns:
        n = _norm_name(col)
        if any(w in n for w in wanted):
            return col
    return None

def _ensure_core_columns(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        raise ValueError("DataFrame is empty or invalid.")

    # store_id
    store_aliases = [
        "store_id", "store id", "store", "store#", "store number", "store_no",
        "storenumber", "storeno", "storecode", "store_code", "location_id",
        "location id", "location"
    ]
    store_col = "store_id" if "store_id" in df.columns else _guess_col(df, store_aliases)
    if not store_col:
        raise ValueError(
            "DataFrame must include a store id column (e.g., 'Store', 'store_id', 'Store #'). "
            f"Found columns: {list(df.columns)}"
        )
    if store_col != "store_id":
        df = df.rename(columns={store_col: "store_id"})

    # Date
    date_aliases = ["date", "Date", "month", "period", "sale_date", "invoice_date"]
    date_col = "Date" if "Date" in df.columns else _guess_col(df, date_aliases)
    if not date_col:
        raise ValueError("DataFrame must include a date column (e.g., 'Date'/'date'/'month').")
    if date_col != "Date":
        df = df.rename(columns={date_col: "Date"})

    # Coerce to datetime only once per process
    flag = "__date_is_dt"
    if not df.attrs.get(flag, False):
        if not pd.api.types.is_datetime64_any_dtype(df["Date"]):
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df.dropna(subset=["Date"], inplace=True)
        df.attrs[flag] = True

    # Optional city/county
    c = _guess_col(df, ["city", "City", "store_city", "city_name"])
    if c and c != "city":
        df = df.rename(columns={c: "city"})
    k = _guess_col(df, ["county", "County", "county_name", "store_county", "countyname"])
    if k and k != "county":
        df = df.rename(columns={k: "county"})

    return df

# ------------------------------- helpers ----------------------------------

def _safe_store_value(v):
    """Return an int if cleanly integral; otherwise return the original (string fallback)."""
    try:
        if isinstance(v, str) and v.isdigit():
            return int(v)
        iv = int(v)
        if float(v) == iv:
            return iv
        return str(v)
    except Exception:
        return str(v)

def _batch_predict(model, latest_rows: pd.DataFrame, features: List[str]) -> List[float]:
    """Predict once; if the model can’t handle it, fallback to _predict_preview per row."""
    X = latest_rows[features]
    try:
        preds = model.predict(X)
        return [float(x) for x in preds]
    except Exception:
        out: List[float] = []
        for _, row in latest_rows.iterrows():
            out.append(float(_predict_preview(model, row.to_frame().T, features)))
        return out

def _pick_latest_numeric_row(row: pd.Series) -> float | None:
    """
    Naïve fallback: pick a reasonable 'latest value' when model features are missing.
    Tries common sales-like columns.
    """
    candidates = [
        "total", "total_sales", "Total_Sales",
        "sales", "Sales", "y", "amount", "sum",
        "revenue", "Revenue", "net_sales", "NetSales", "GrossSales",
        "Bottles Sold", "Bottles_Sold",
    ]
    for c in candidates:
        if c in row:
            try:
                return float(row[c])
            except Exception:
                continue
    return None

# -------------------------------- route ------------------------------------

@store_bp.route("/api/stores", methods=["GET"])
def get_stores():
    """
    Fast store list:
      • If model features exist → single batched prediction (very fast).
      • If features missing → graceful fallback to a naïve latest numeric value (never 500).
    Query:
      - min_year  (int, default 2020)
      - min_points(int, default 5)
      - limit     (int, optional)
    """
    logger: logging.Logger = current_app.logger
    t0 = time.time()

    try:
        # 1) Core objects
        _ensure_required_objects(current_app.config)
        df: pd.DataFrame = current_app.config["df"]
        model = current_app.config["model"]
        features: List[str] = list(current_app.config["model_features"])

        # 2) Params
        min_year = request.args.get("min_year", default=2020, type=int)
        min_points = request.args.get("min_points", default=5, type=int)
        limit = request.args.get("limit", type=int)

        # 3) Normalize columns + Date
        df = _ensure_core_columns(df)

        # Cache key
        df_id = id(df)
        df_version = getattr(df, "version", (df.shape, tuple(df.columns)))
        feature_sig = tuple(features)
        cache_key = (min_year, min_points, limit, df_id, df_version, feature_sig)

        now = time.time()
        hit = _STORES_CACHE.get(cache_key)
        if hit and (now - hit[0] < _CACHE_TTL_SEC):
            return jsonify(hit[1]), 200

        # 4) Filter by year
        df2 = df[df["Date"].dt.year >= min_year]
        if df2.empty:
            _STORES_CACHE[cache_key] = (now, [])
            return jsonify([]), 200

        # 5) Require min distinct months per store
        months_per_store = (
            df2.assign(_m=df2["Date"].dt.to_period("M"))
               .groupby("store_id")["_m"]
               .nunique()
        )
        ok_store_ids = set(months_per_store[months_per_store >= min_points].index)
        if not ok_store_ids:
            _STORES_CACHE[cache_key] = (now, [])
            return jsonify([]), 200

        df2 = df2[df2["store_id"].isin(ok_store_ids)]

        # 6) Latest row per store
        idx = df2.groupby("store_id")["Date"].idxmax()
        latest_rows = df2.loc[idx].copy()

        # 7) Human labels
        def make_label(row: pd.Series) -> str:
            sid = _safe_store_value(row["store_id"])
            city = str(row.get("city", "")).strip() if "city" in row else ""
            county = str(row.get("county", "")).strip() if "county" in row else ""
            if city and county:
                return f"Store {sid} – {city}, {county}"
            if city:
                return f"Store {sid} – {city}"
            return f"Store {sid}"

        latest_rows["__label"] = latest_rows.apply(make_label, axis=1)

        # 8) If any model features missing → naïve fallback (NO ERROR)
        missing = [f for f in features if f not in latest_rows.columns]
        if missing:
            logger.warning(
                "Model features missing from latest_rows: %s. "
                "Using naïve latest-value preview for /api/stores.",
                missing,
            )

            if limit and limit > 0:
                latest_rows = latest_rows.head(limit)

            out = []
            # iterate as Series so we can access '__label' safely
            for _, r in latest_rows.iterrows():
                preview = _pick_latest_numeric_row(r)
                out.append({
                    "value": _safe_store_value(r["store_id"]),
                    "label": r["__label"],
                    "forecast": preview  # may be None; UI can handle/null-coalesce
                })

            _STORES_CACHE[cache_key] = (now, out)
            logger.info("GET /api/stores (naïve) → %d stores in %.1f ms",
                        len(out), (time.time() - t0) * 1000)
            return jsonify(out), 200

        # 9) Model path: drop NaNs in required features, optional limit, single predict
        latest_rows = latest_rows.dropna(subset=features)
        if latest_rows.empty:
            _STORES_CACHE[cache_key] = (now, [])
            return jsonify([]), 200

        if limit and limit > 0:
            latest_rows = latest_rows.head(limit)

        preds = _batch_predict(model, latest_rows, features)

        # Build lists directly from DF to avoid attribute issues
        ids = latest_rows["store_id"].tolist()
        labels = latest_rows["__label"].tolist()

        out = [
            {"value": _safe_store_value(sid), "label": lbl, "forecast": float(p)}
            for sid, lbl, p in zip(ids, labels, preds)
        ]

        _STORES_CACHE[cache_key] = (now, out)
        logger.info("GET /api/stores → %d stores in %.1f ms",
                    len(out), (time.time() - t0) * 1000)
        return jsonify(out), 200

    except ValueError as ve:
        logger.error("Configuration/Data error in /api/stores: %s", ve)
        return jsonify({"error": str(ve)}), 500
    except Exception:
        logger.exception("Failed to load store list")
        return jsonify({"error": "Failed to load store list"}), 500
