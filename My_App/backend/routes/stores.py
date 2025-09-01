from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request
from typing import List, Dict
import logging, time
import pandas as pd

from .data_access import (
    _ensure_required_objects,
    _iter_unique_stores,
    _prepare_store_timeseries,
    _has_min_months,
    _predict_preview,
)

store_bp = Blueprint("store", __name__)

# ---- tiny in-process cache (per worker) ----
_STORES_CACHE: Dict = {}
_CACHE_TTL_SEC = 60 * 60  # 1 hour


# ----------------------------
# Returns a list of stores with basic details and (optionally) a single-step
# forecast preview.
#
# Input (query params):
#   - min_year (int): Earliest year of sales data to include (default: 2020)
#   - min_points (int): Minimum number of months required for a store (default: 5)
#   - limit (int): Maximum number of stores to return (optional)
#   - preview (bool-ish): true/1/yes → include 'forecast' (calls _predict_preview).
#                         Default is false for speed.
#
# Returns:
#   - JSON list of objects:
#       { value: <int>, label: "Store <id> – CITY, COUNTY", [forecast: <float>] }
#
# Implementation notes:
#   - Keeps your original per-store workflow and helpers (no schema surprises).
#   - Adds caching, early exit, and optional forecast to cut latency.
# ----------------------------
@store_bp.route("/api/stores", methods=["GET"])
def get_stores():
    logger: logging.Logger = current_app.logger

    try:
        _ensure_required_objects(current_app.config)

        df: pd.DataFrame = current_app.config["df"]
        model = current_app.config["model"]
        features: List[str] = list(current_app.config["model_features"])

        # Parse query params with safe defaults
        min_year   = request.args.get("min_year",   default=2020, type=int)
        min_points = request.args.get("min_points", default=5,    type=int)
        limit      = request.args.get("limit",      type=int)
        preview    = str(request.args.get("preview", "0")).lower() in ("1", "true", "yes", "y")

        # Cache lookup
        cache_key = ("stores_v1", min_year, min_points, limit, preview)
        now = time.time()
        cached = _STORES_CACHE.get(cache_key)
        if cached and now - cached["t"] < _CACHE_TTL_SEC:
            return jsonify(cached["v"]), 200

        results: List[Dict] = []
        # Iterate using your existing metadata helper
        for meta in _iter_unique_stores(df):
            store_id = meta["store_id"]
            city     = meta.get("city", "")
            county   = meta.get("county", "")

            try:
                # Prepare timeseries for this store (keeps your original behavior)
                store_df = _prepare_store_timeseries(df, store_id, min_year=min_year)
                if not _has_min_months(store_df, min_points=min_points):
                    continue

                # Get most recent row
                latest = store_df.sort_values("Date").tail(1).copy()

                # Forecast only when preview=true (the heavy step)
                item: Dict = {"value": store_id, "label": f"Store {store_id} – {city}, {county}"}
                if preview:
                    try:
                        item["forecast"] = _predict_preview(model, latest, features)
                    except Exception as pex:
                        # Don’t fail the whole list if one store’s preview fails
                        logger.warning("Preview predict failed for store %s: %s", store_id, pex)

                results.append(item)

                # Early exit when limit is reached (avoids looping all stores)
                if limit is not None and limit > 0 and len(results) >= limit:
                    break

            except Exception as ex:
                # Skip bad stores but keep the endpoint healthy
                logger.warning("Skipping store %s due to error: %s", store_id, ex)
                continue

        # If no explicit limit (or fewer than limit), return all we collected
        # (No slice needed thanks to the break above.)

        # Cache and return
        _STORES_CACHE[cache_key] = {"t": now, "v": results}
        return jsonify(results), 200

    except ValueError as ve:
        logger.error("Configuration/Data error in /api/stores: %s", ve)
        return jsonify({"error": str(ve)}), 500
    except Exception as e:
        logger.exception("Failed to load store list")
        return jsonify({"error": "Failed to load store list"}), 500
