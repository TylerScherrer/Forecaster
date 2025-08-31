from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request
from typing import List, Dict
import logging
import pandas as pd

# import helpers from services while keeping your original names/docs
from .data_access import (
    _ensure_required_objects,
    _iter_unique_stores,
    _prepare_store_timeseries,
    _has_min_months,
    _predict_preview,
)

store_bp = Blueprint("store", __name__)

# ----------------------------
# Returns a list of stores with basic details and a single-step forecast preview.
# Input:
#   - None directly from the function call, but uses:
#       - Flask's `current_app.config` to access `df`, `model`, and `model_features`
#       - Optional query parameters:
#           - min_year (int): Earliest year of sales data to include (default: 2020)
#           - min_points (int): Minimum number of months required for a store (default: 5)
#           - limit (int): Maximum number of stores to return (optional)
#
# Returns:
#   - JSON list of objects, each containing:
#       - value (int): Store ID
#       - label (str): "Store <id> – CITY, COUNTY"
#       - forecast (float): Predicted sales value from the model
#
# Details:
#   1. Validate that required objects (df, model, features) exist in `app.config`.
#   2. Read query parameters for filtering options.
#   3. Iterate over all unique stores from the DataFrame.
#   4. For each store:
#        a. Filter the store's sales data to the given year range.
#        b. Ensure the store has the required minimum months of data.
#        c. Get the most recent row and run `_predict_preview` to get forecast.
#        d. Append store details and forecast to the results list.
#   5. Return the final list as a JSON response.
# ----------------------------
@store_bp.route("/api/stores", methods=["GET"])
def get_stores():
    logger: logging.Logger = current_app.logger  # Used to write log messages

    try:
        _ensure_required_objects(current_app.config)  # Validates that all required objects for the app exist and are correctly formatted.
        df: pd.DataFrame = current_app.config["df"]
        model = current_app.config["model"]
        features: List[str] = list(current_app.config["model_features"])

        # Parse query params with safe defaults
        min_year = request.args.get("min_year", default=2020, type=int)  # is a dictionary-like object Flask gives you that contains all query parameters from the URL.
        min_points = request.args.get("min_points", default=5, type=int)
        limit = request.args.get("limit", type=int)

        results: List[Dict] = []  # list of store dictionaries, containing each store's keys (value, label, forecast)

        # For each store dictionary from _iter_unique_stores, pull out the store ID, city, and county into their own variables so we can use them for filtering and labeling.
        for meta in _iter_unique_stores(df):
            store_id = meta["store_id"]
            city = meta["city"]
            county = meta["county"]

            try:
                # Returns filtered DataFrame with
                # Only rows for this store
                # Only rows from min_year and later
                # With the Date column converted to datetime
                # Without invalid dates
                store_df = _prepare_store_timeseries(df, store_id, min_year=min_year)

                if not _has_min_months(store_df, min_points=min_points):
                    # Not enough recent monthly data; skip from dropdown
                    continue

                latest = store_df.sort_values("Date").tail(1).copy()  # Sorts the DataFrame by Data, Takes the last 1 row (which is now the newest), and makes a copy
                forecast = _predict_preview(model, latest, features)  # Generates a single forecast value using the most recent store data row.
                label = f"Store {store_id} – {city}, {county}"  # Creates a label for the store using its ID, city, and county.

                results.append(
                    {"value": store_id, "label": label, "forecast": forecast}  # Add a new entry to our growing list of store options, including its ID, display name, and forecasted sales
                )
            except Exception as ex:
                # Skip bad stores but keep the endpoint healthy
                logger.warning("Skipping store %s due to error: %s", store_id, ex)
                continue

        if limit is not None and limit > 0:  # If the user asked for a maximum number of stores, trim the results list so it only has that many entries
            results = results[:limit]  # means “take only the first limit items from results"

        return jsonify(results), 200

    except ValueError as ve:
        logger.error("Configuration/Data error in /api/stores: %s", ve)
        return jsonify({"error": str(ve)}), 500
    except Exception as e:
        logger.exception("Failed to load store list")
        return jsonify({"error": "Failed to load store list"}), 500
