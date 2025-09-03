# backend/routes/forecast.py
from __future__ import annotations

from flask import Blueprint, current_app, jsonify
from typing import List, Dict
import pandas as pd

from .data_access import _ensure_required_objects

forecast_bp = Blueprint("forecast", __name__)

def _label(dt: pd.Timestamp) -> str:
    return dt.strftime("%b %y")

@forecast_bp.route("/api/forecast/<int:store_id>", methods=["GET"])
def get_forecast_for_store(store_id: int):
    try:
        _ensure_required_objects(current_app.config)
    except ValueError as e:
        return jsonify({"error": str(e)}), 500

    df: pd.DataFrame = current_app.config.get("df")
    model = current_app.config.get("model")
    features: List[str] = list(current_app.config.get("model_features", []))
    category_features: List[str] = list(current_app.config.get("category_features", []))

    if df is None or model is None:
        return jsonify({"error": "Required data not loaded"}), 500

    log = current_app.logger

    try:
        df = df.copy()

        # 1) Normalize store id column
        store_aliases = [
            "Store Number", "store_id", "Store", "Store #", "StoreNumber",
            "Location ID", "LocationID", "location_id", "store"
        ]
        store_col = next((c for c in store_aliases if c in df.columns), None)
        if not store_col:
            log.warning("No recognizable store column. Columns=%s", list(df.columns)[:20])
            return jsonify({"history": [], "forecast": []}), 200
        if store_col != "Store Number":
            df.rename(columns={store_col: "Store Number"}, inplace=True)

        # 2) Normalize totals column
        total_aliases = ["Total_Sales", "Total Sales", "total_sales", "Sales"]
        total_col = next((c for c in total_aliases if c in df.columns), None)
        if not total_col:
            log.warning("No recognizable total-sales column. Columns=%s", list(df.columns)[:20])
            return jsonify({"history": [], "forecast": []}), 200
        if total_col != "Total_Sales":
            df.rename(columns={total_col: "Total_Sales"}, inplace=True)

        # 3) Coerce types
        df["Store Number"] = pd.to_numeric(df["Store Number"], errors="coerce")
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df.dropna(subset=["Store Number", "Date"], inplace=True)
        df["Store Number"] = df["Store Number"].astype(int)

        # 4) Filter this store and time window
        store_df = df[df["Store Number"] == int(store_id)].sort_values("Date")
        if store_df.empty:
            log.info("No rows for store %s after normalization", store_id)
            return jsonify({"history": [], "forecast": []}), 200
        store_df = store_df[store_df["Date"].dt.year >= 2020]

        # 5) Month bucket
        store_df["YearMonth"] = store_df["Date"].dt.to_period("M").dt.to_timestamp()

        # 6) Monthly totals
        monthly_total = store_df.groupby("YearMonth")["Total_Sales"].sum().reset_index()
        monthly_total.columns = ["date", "total_sales"]

        # 7) Monthly categories (optional)
        avail_cats = [c for c in category_features if c in store_df.columns]
        if avail_cats:
            cat_df = store_df[["YearMonth"] + avail_cats].groupby("YearMonth").sum().reset_index()
            cat_df["date"] = pd.to_datetime(cat_df["YearMonth"])
            cat_df.drop(columns=["YearMonth"], inplace=True)
        else:
            cat_df = pd.DataFrame(columns=["date"])

        # 8) History points (last 5 months)
        history: List[Dict] = []
        for _, row in monthly_total.iterrows():
            dt: pd.Timestamp = row["date"]
            cats = cat_df[cat_df["date"] == dt]
            cats_dict = (cats.drop(columns=["date"]).to_dict("records")[0] if not cats.empty else {})
            history.append({
                "date": dt.strftime("%Y-%m-%d"),
                "label": _label(dt),
                "total_sales": round(float(row["total_sales"]), 2),
                "source": "history",
                "categories": {k.replace("_Sales", ""): round(float(v), 2) for k, v in cats_dict.items()},
            })

        history = sorted(history, key=lambda x: x["date"])[-5:]
        if len(history) < 2:
            log.info("Store %s has <2 months after grouping; returning empty forecast", store_id)
            return jsonify({"history": [], "forecast": []}), 200

        # 9) Forecast one month ahead (pad missing features with 0.0)
        latest_dt = pd.to_datetime(history[-1]["date"])
        latest_full = store_df.iloc[-1:].copy()
        for col in features:
            if col not in latest_full.columns:
                latest_full[col] = 0.0

        yhat = float(model.predict(latest_full[features])[0])
        next_dt = (latest_dt + pd.DateOffset(months=1)).normalize()

        forecast_point = {
            "date": next_dt.strftime("%Y-%m-%d"),
            "label": _label(next_dt),
            "predicted": round(yhat, 2),  # for chart code that expects 'predicted'
            "sales": round(yhat, 2),      # for anything that reads 'sales'
            "source": "forecast",
        }

        payload = {"history": history, "forecast": [forecast_point]}
        log.info("Forecast payload for store %s -> hist=%d, forecast=1", store_id, len(history))
        return jsonify(payload), 200

    except Exception:
        log.exception("Forecast route error for store %s", store_id)
        return jsonify({"error": "Failed to generate forecast"}), 500
