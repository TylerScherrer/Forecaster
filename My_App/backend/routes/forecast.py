from __future__ import annotations

from flask import Blueprint, current_app, jsonify
from typing import List
import pandas as pd

# import helpers from services while keeping your original names/docs
from .data_access import _ensure_required_objects

forecast_bp = Blueprint("forecast", __name__)

# ----------------------------
# Returns historical sales data and forecast values for a given store.
# Input:
#   - store_id (int): The ID of the store, passed in the URL path
#     (e.g., /api/forecast/101)
#
# Returns:
#   - JSON object with:
#       - "history": List of historical sales records (date and sales value)
#       - "forecast": List of forecasted sales values for upcoming periods
#
# Details:
#   1. Validate that required objects (df, model, model_features) exist in app.config.
#   2. Filter the DataFrame for the given store ID.
#   3. Prepare and format historical sales data for output.
#   4. Run the forecasting model to generate predicted values.
#   5. Return both the historical data and forecast as a JSON response.
# ----------------------------
@forecast_bp.route("/api/forecast/<int:store_id>", methods=["GET"])
def get_forecast_for_store(store_id):
    try:
        _ensure_required_objects(current_app.config)  # Validates that all required objects for the app exist and are correctly formatted.
    except ValueError as e:
        return jsonify({"error": str(e)}), 500

    df = current_app.config.get("df")
    model = current_app.config.get("model")
    features = current_app.config.get("model_features")
    category_features = current_app.config.get("category_features", [])

    if df is None or model is None:
        return jsonify({"error": "Required data not loaded"}), 500

    try:
        store_df = df[df["Store Number"] == store_id].copy()  # Filter the DataFrame for the given store ID
        store_df["Date"] = pd.to_datetime(store_df["Date"], errors="coerce")  # Convert the "Date" column to datetime
        store_df = store_df[store_df["Date"].dt.year >= 2020]  # Keep only rows from 2020 onwards
        store_df["YearMonth"] = store_df["Date"].dt.to_period("M").dt.to_timestamp()  # Create a YearMonth column

        monthly_total = store_df.groupby("YearMonth")["Total_Sales"].sum().reset_index()  # Total monthly sales
        # .reset_index() takes any values currently acting as the DataFrame’s row labels (index) and moves them back into normal columns so you can treat them like regular data
        monthly_total.columns = ["date", "total_sales"]  # Rename columns for clarity

        available_categories = [col for col in category_features if col in store_df.columns]  # Identify available category features
        if not available_categories:
            print(f"No category features available for store {store_id}")
            monthly_categories = pd.DataFrame(columns=["date"])  # Create empty DataFrame for categories
        else:
            category_df = store_df[["YearMonth"] + available_categories].copy()  # Create DataFrame for available categories
            monthly_categories = category_df.groupby("YearMonth").sum().reset_index()  # Total monthly sales by category
            monthly_categories["date"] = pd.to_datetime(monthly_categories["YearMonth"])  # Convert YearMonth to datetime
            monthly_categories.drop(columns=["YearMonth"], inplace=True)  # Drop the YearMonth column

        history = []  # Initialize history list
        for _, row in monthly_total.iterrows():  # Iterate over monthly total sales
            date = row["date"]  # Get the date
            total = row["total_sales"]  # Get the total sales

            cat_row = monthly_categories[monthly_categories["date"] == date]  # Get category row for the date
            categories = (
                cat_row.drop(columns=["date"]).to_dict("records")[0]  # Get category sales for the date
                if not cat_row.empty else {}  # Create empty dict if no categories found
            )

            history.append({
                "date": date.strftime("%Y-%m-%d"),
                "total_sales": round(total, 2),  # Round total sales to 2 decimal places
                "categories": {
                    k.replace("_Sales", ""): round(v, 2) for k, v in categories.items()  # Round category sales to 2 decimal places
                }
            })

        total_by_category = {}  # Initialize category totals
        for record in history:
            for category, amount in record["categories"].items():  # Sum total sales by category
                total_by_category[category] = total_by_category.get(category, 0) + amount  # Update category total

        # Keep only top 9 categories
        top_categories = sorted(total_by_category, key=total_by_category.get, reverse=True)[:9]

        for record in history:
            record["categories"] = {
                cat: val for cat, val in record["categories"].items() if cat in top_categories  # Keep only top categories
            }

        history = sorted(history, key=lambda x: x["date"])[-5:]  # Keep only last 5 months

        if len(history) < 2:  # Check if there are at least 2 months of data
            print(f"Skipping forecast for store {store_id} (insufficient recent data)")
            return jsonify({"history": [], "forecast": []})

        latest = store_df.sort_values("Date").iloc[-1:].copy()  # Get latest month data
        for col in features:  # Ensure all features are present
            if col not in latest.columns:  # Add missing columns with 0 values
                latest[col] = 0  # Add missing columns with 0 values

        forecast_value = float(model.predict(latest[features])[0])  # Get forecast value
        next_month = (pd.to_datetime(history[-1]["date"]) + pd.DateOffset(months=1)).strftime("%Y-%m")  # Get next month

        return jsonify({
            "history": history,
            "forecast": [{"date": next_month, "sales": round(forecast_value, 2)}]
        })

    except Exception as e:
        print(f"Forecast route error for store {store_id}: {e}")
        return jsonify({"error": "Failed to generate forecast"}), 500
