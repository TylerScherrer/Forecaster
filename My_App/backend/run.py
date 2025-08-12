from flask import Flask
from flask_cors import CORS
from backend.routes import register_routes
import pandas as pd
import pickle
from pathlib import Path

app = Flask(__name__)
CORS(app)

# Base directory of this file (…/My_App/backend)
BASE_DIR = Path(__file__).resolve().parent

# ✅ Load data/model using paths relative to run.py
features_path = BASE_DIR / "features.csv"
model_path = BASE_DIR / "model.pkl"

if not features_path.exists():
    raise FileNotFoundError(f"features.csv not found at: {features_path}")
if not model_path.exists():
    raise FileNotFoundError(f"model.pkl not found at: {model_path}")

df = pd.read_csv(features_path)

with open(model_path, "rb") as f:
    model = pickle.load(f)

model_features = [
    'Lag_1','Lag_2','Lag_3','Rolling_3','Rolling_6','Rolling_12',
    'Rolling_Trend','Month','Quarter','IsYearStart','IsYearEnd',
    'AvgPricePerBottle','MarginRatio','UniqueProductsSold',
    'Bottles Sold','IsHolidayMonth'
]

category_features = [c for c in df.columns if c.endswith("_Sales") and c != "Total_Sales"]

# Put into app.config
app.config["df"] = df
app.config["model"] = model
app.config["model_features"] = model_features
app.config["category_features"] = category_features

# Register all blueprints
register_routes(app)

if __name__ == "__main__":
    app.run(debug=True)
