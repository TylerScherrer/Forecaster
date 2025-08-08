from flask import Flask
from flask_cors import CORS
from routes import register_routes
from routes.explain_forecast import explain_bp


import pandas as pd
import pickle

app = Flask(__name__)
CORS(app)

# ✅ Load data
df = pd.read_csv("features.csv")

# ✅ Load model
with open("model.pkl", "rb") as f:
    model = pickle.load(f)

# ✅ Define model features
model_features = [
    'Lag_1', 'Lag_2', 'Lag_3', 'Rolling_3', 'Rolling_6', 'Rolling_12',
    'Rolling_Trend', 'Month', 'Quarter', 'IsYearStart', 'IsYearEnd',
    'AvgPricePerBottle', 'MarginRatio', 'UniqueProductsSold',
    'Bottles Sold', 'IsHolidayMonth'
]

# ✅ Dynamically detect category columns
category_features = [
    col for col in df.columns
    if col.endswith("_Sales") and col != "Total_Sales"
]

# ✅ Store in app config
app.config["df"] = df
app.config["model"] = model
app.config["model_features"] = model_features
app.config["category_features"] = category_features

# ✅ Register routes and blueprints
register_routes(app)
app.register_blueprint(explain_bp)

if __name__ == "__main__":
    app.run(debug=True)
