# backend/routes/forecast.py
from __future__ import annotations

from flask import Blueprint, current_app, jsonify
from typing import List, Dict
import pandas as pd

from .data_access import _ensure_required_objects

forecast_bp = Blueprint("forecast", __name__)

def _label(dt: pd.Timestamp) -> str:
  # stable "Mon YY" label using pandas timestamp (no TZ issues)
  return dt.strftime("%b %y")

@forecast_bp.route("/api/forecast/<int:store_id>", methods=["GET"])
def get_forecast_for_store(store_id: int):
    try:
        _ensure_required_objects(current_app.config)
    except ValueError as e:
        return jsonify({"error": str(e)}), 500

    df: pd.DataFrame = current_app.config.get("df")
    model = current_app.config.get("model")
    features: List[str] = current_app.config.get("model_features", [])
    category_features: List[str] = current_app.config.get("category_features", [])

    if df is None or model is None:
        return jsonify({"error": "Required data not loaded"}), 500

    try:
        store_df = df[df["Store Number"] == store_id].copy()
        store_df["Date"] = pd.to_datetime(store_df["Date"], errors="coerce")
        store_df = store_df.dropna(subset=["Date"])
        store_df = store_df[store_df["Date"].dt.year >= 2020]

        # month bucket (month start)
        store_df["YearMonth"] = store_df["Date"].dt.to_period("M").dt.to_timestamp()

        # Monthly totals
        monthly_total = store_df.groupby("YearMonth")["Total_Sales"].sum().reset_index()
        monthly_total.columns = ["date", "total_sales"]

        # Categories (optional)
        available_categories = [c for c in category_features if c in store_df.columns]
        if available_categories:
            category_df = store_df[["YearMonth"] + available_categories].copy()
            monthly_categories = category_df.groupby("YearMonth").sum().reset_index()
            monthly_categories["date"] = pd.to_datetime(monthly_categories["YearMonth"])
            monthly_categories.drop(columns=["YearMonth"], inplace=True)
        else:
            monthly_categories = pd.DataFrame(columns=["date"])

        # Build history with consistent label + source
        history: List[Dict] = []
        for _, row in monthly_total.iterrows():
            dt: pd.Timestamp = row["date"]
            total = row["total_sales"]

            cat_row = monthly_categories[monthly_categories["date"] == dt]
            categories = (
                cat_row.drop(columns=["date"]).to_dict("records")[0]
                if not cat_row.empty else {}
            )

            history.append({
                "date": dt.strftime("%Y-%m-%d"),
                "label": _label(dt),
                "total_sales": round(float(total), 2),
                "source": "history",
                "categories": {k.replace("_Sales", ""): round(float(v), 2) for k, v in categories.items()},
            })

        # keep last 5 months for the UI
        history = sorted(history, key=lambda x: x["date"])[-5:]

        if len(history) < 2:
            return jsonify({"history": [], "forecast": []})

        # Prepare a single-row feature frame for prediction
        latest_row_dt = pd.to_datetime(history[-1]["date"])
        latest_full = store_df.sort_values("Date").iloc[-1:].copy()
        for col in features:
            if col not in latest_full.columns:
                latest_full[col] = 0.0

        forecast_value = float(model.predict(latest_full[features])[0])
        next_month_dt = (latest_row_dt + pd.DateOffset(months=1)).normalize()

        forecast = [{
            "date": next_month_dt.strftime("%Y-%m-%d"),
            "label": _label(next_month_dt),
            "sales": round(forecast_value, 2),
            "source": "forecast",
        }]

        return jsonify({"history": history, "forecast": forecast})

    except Exception as e:
        current_app.logger.exception("Forecast route error for store %s", store_id)
        return jsonify({"error": "Failed to generate forecast"}), 500
