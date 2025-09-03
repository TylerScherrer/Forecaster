# run.py
from __future__ import annotations
import os
from flask import Flask, jsonify
from flask_cors import CORS

# IMPORTANT: this lives in backend/routes/data_access.py
# If your layout differs, adjust the import path accordingly.
from routes.data_access import load_artifacts_into_config
from routes import register_routes

app = Flask(__name__)
CORS(app)

# Load df/model once at boot (uses cached files in /home/site/data)
with app.app_context():
    load_artifacts_into_config(app.config)

# Simple health probe
@app.get("/api/health")
def health():
    cfg = app.config
    df = cfg.get("df")
    return jsonify(
        ok=True,
        rows=int(len(df)) if df is not None else 0,
        model_loaded=bool(cfg.get("model")),
        features=len(cfg.get("model_features", [])),
    ), 200

# Your API routes
register_routes(app)

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
