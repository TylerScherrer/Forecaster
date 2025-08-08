from flask import Blueprint, jsonify, current_app
import pandas as pd

store_bp = Blueprint("store", __name__)

@store_bp.route("/api/stores", methods=["GET"])
def get_stores():
    df = current_app.config.get("df")
    model = current_app.config.get("model")
    features = current_app.config.get("model_features")

    if df is None or model is None:
        return jsonify({"error": "Required data not loaded"}), 500

    try:
        stores = df[["Store Number", "City", "County"]].dropna().drop_duplicates()
        stores = stores.sort_values("Store Number")

        results = []

        for _, row in stores.iterrows():
            try:
                store_id = int(row["Store Number"])
                city = row["City"].upper()
                county = row["County"].upper()
                label = f"Store {store_id} – {city}, {county}"

                # ✅ Filter and prepare store data
                store_df = df[df["Store Number"] == store_id].copy()
                store_df["Date"] = pd.to_datetime(store_df["Date"], errors="coerce")
                store_df = store_df[store_df["Date"].dt.year >= 2020]

                store_df["YearMonth"] = store_df["Date"].dt.to_period("M").dt.to_timestamp()
                monthly = store_df.groupby("YearMonth")["Total_Sales"].sum().reset_index()

                if len(monthly) < 5:
                    print(f"⏭️ Skipping store {store_id} from dropdown (insufficient recent data)")
                    continue  # ❌ Don't add to results

                # ✅ Get latest row for forecast preview
                latest = store_df.sort_values("Date").iloc[-1:].copy()
                for col in features:
                    if col not in latest.columns:
                        latest[col] = 0

                forecast = round(float(model.predict(latest[features])[0]), 2)

                results.append({
                    "value": store_id,
                    "label": label,
                    "forecast": forecast
                })

            except Exception as e:
                print(f"⚠️ Error processing store {row['Store Number']}: {e}")
                continue

        return jsonify(results)

    except Exception as e:
        print(f"❌ Error generating store list: {e}")
        return jsonify({"error": "Failed to load store list"}), 500


@store_bp.route("/api/forecast/<int:store_id>", methods=["GET"])
def get_forecast_for_store(store_id):
    df = current_app.config.get("df")
    model = current_app.config.get("model")
    features = current_app.config.get("model_features")
    category_features = current_app.config.get("category_features", [])

    if df is None or model is None:
        return jsonify({"error": "Required data not loaded"}), 500

    try:
        # Filter and prep
        store_df = df[df["Store Number"] == store_id].copy()
        store_df["Date"] = pd.to_datetime(store_df["Date"], errors="coerce")
        store_df = store_df[store_df["Date"].dt.year >= 2020]
        store_df["YearMonth"] = store_df["Date"].dt.to_period("M").dt.to_timestamp()

        # Total monthly sales
        monthly_total = store_df.groupby("YearMonth")["Total_Sales"].sum().reset_index()
        monthly_total.columns = ["date", "total_sales"]

        # Prepare category breakdown
        available_categories = [col for col in category_features if col in store_df.columns]
        if not available_categories:
            print(f"⚠️ No category features available for store {store_id}")
            monthly_categories = pd.DataFrame(columns=["date"])
        else:
            category_df = store_df[["YearMonth"] + available_categories].copy()
            monthly_categories = category_df.groupby("YearMonth").sum().reset_index()
            monthly_categories["date"] = pd.to_datetime(monthly_categories["YearMonth"])
            monthly_categories.drop(columns=["YearMonth"], inplace=True)

        # Build full history (initial pass)
        history = []
        for _, row in monthly_total.iterrows():
            date = row["date"]
            total = row["total_sales"]

            cat_row = monthly_categories[monthly_categories["date"] == date]
            categories = (
                cat_row.drop(columns=["date"]).to_dict("records")[0]
                if not cat_row.empty else {}
            )

            history.append({
                "date": date.strftime("%Y-%m-%d"),
                "total_sales": round(total, 2),
                "categories": {
                    k.replace("_Sales", ""): round(v, 2) for k, v in categories.items()
                }
            })

        # ✅ Sum category totals across all months
        total_by_category = {}
        for record in history:
            for category, amount in record["categories"].items():
                total_by_category[category] = total_by_category.get(category, 0) + amount

        # ✅ Keep only top 9 categories
        top_categories = sorted(total_by_category, key=total_by_category.get, reverse=True)[:9]

        for record in history:
            record["categories"] = {
                cat: val for cat, val in record["categories"].items() if cat in top_categories
            }

        # ✅ Only keep last 5 months
        history = sorted(history, key=lambda x: x["date"])[-5:]

        if len(history) < 2:
            print(f"⏭️ Skipping forecast for store {store_id} (insufficient recent data)")
            return jsonify({"history": [], "forecast": []})

        # Forecast
        latest = store_df.sort_values("Date").iloc[-1:].copy()
        for col in features:
            if col not in latest.columns:
                latest[col] = 0

        forecast_value = float(model.predict(latest[features])[0])
        next_month = (pd.to_datetime(history[-1]["date"]) + pd.DateOffset(months=1)).strftime("%Y-%m")

        return jsonify({
            "history": history,
            "forecast": [{"date": next_month, "sales": round(forecast_value, 2)}]
        })

    except Exception as e:
        print(f"❌ Forecast route error for store {store_id}: {e}")
        return jsonify({"error": "Failed to generate forecast"}), 500
