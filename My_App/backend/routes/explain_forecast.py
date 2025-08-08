from flask import Blueprint, request, jsonify
import requests
import os

explain_bp = Blueprint("explain_forecast", __name__)

@explain_bp.route("/api/explain_forecast", methods=["POST"])
def explain_forecast():
    try:
        data = request.get_json()
        print(f"🧾 Raw incoming data type: {type(data)}")

        # Step 1: Handle both old and new formats
        if isinstance(data, list):
            timeline = data
        elif isinstance(data, dict) and "timeline" in data:
            timeline = data["timeline"]
        else:
            print("❌ Invalid data structure received.")
            return jsonify({"error": "Expected a list or dict with 'timeline' key"}), 400

        print(f"🧾 Timeline type: {type(timeline)}")
        print("🧾 First entry:", timeline[0] if timeline else "Empty")

        if not isinstance(timeline, list) or len(timeline) < 1:
            return jsonify({"error": "Timeline must be a non-empty list"}), 400

        forecast_part = timeline[-4:]

        # Step 2: Defensive check for valid structure
        first_entry = forecast_part[0]
        if not isinstance(first_entry, dict):
            print("❌ Forecast entry is not a dictionary.")
            return jsonify({"error": "Forecast entries must be dictionaries"}), 400

        # Step 3: Figure out which key to use: 'sales' or 'total_sales'
        if "sales" in first_entry:
            sales_key = "sales"
        elif "total_sales" in first_entry:
            sales_key = "total_sales"
        else:
            print("❌ Neither 'sales' nor 'total_sales' key found.")
            return jsonify({"error": "Forecast entries must contain 'sales' or 'total_sales'"}), 400

        # Step 4: Build prompt safely
        try:
            forecast_lines = "\n".join([
                f"{entry['date']}: ${entry[sales_key]}"
                for entry in forecast_part
                if isinstance(entry, dict) and 'date' in entry and sales_key in entry
            ])
        except Exception as e:
            print(f"❌ Error formatting forecast lines: {e}")
            return jsonify({"error": "Failed to format forecast for prompt"}), 400

        prompt = (
            "Explain this liquor sales forecast simply to a store manager with no data background:\n\n"
            + forecast_lines
        )

        payload = {
            "model": "llama3-8b-8192",
            "messages": [
                {"role": "system", "content": "You are a helpful retail analyst."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 300
        }

        headers = {
            "Authorization": f"Bearer {os.environ.get('GROQ_API_KEY')}",
            "Content-Type": "application/json"
        }

        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload
        )

        if response.status_code != 200:
            print("❌ Groq API error:", response.text)
            return jsonify({"error": "Groq model request failed"}), 500

        explanation = response.json()["choices"][0]["message"]["content"]
        print("📬 AI Explanation:", explanation)

        return jsonify({"summary": explanation.strip()})

    except Exception as e:
        print(f"🔥 Unexpected error in /api/explain_forecast: {e}")
        return jsonify({"error": "Failed to generate explanation"}), 500
