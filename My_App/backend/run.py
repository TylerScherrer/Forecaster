# run.py
import os
import sys
import pickle
from io import BytesIO
from pathlib import Path
import pandas as pd
from flask import Flask, jsonify
from flask_cors import CORS

# Optional: only needed if we pull from Azure Blob
try:
    from azure.storage.blob import BlobClient
    HAS_AZURE = True
except Exception:
    HAS_AZURE = False

app = Flask(__name__)
CORS(app)

# ---- Paths (Azure unpacks your app under /home/site/wwwroot) ----
BASE_DIR = Path(__file__).resolve().parent
WWWROOT  = Path("/home/site/wwwroot")

# Ensure current directory is importable (so we can `import routes`)
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# ---- App Settings (Portal → Configuration) ----
AZURE_CONN    = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")
AZURE_CONT    = os.getenv("AZURE_STORAGE_CONTAINER", "artifacts")
FEATURES_BLOB = os.getenv("FEATURES_BLOB_NAME", "features.csv")
MODEL_BLOB    = os.getenv("MODEL_BLOB_NAME", "model.pkl")

# If you want to force download+cache instead of in-memory load:
# set BLOB_CACHE_ON_DISK=1 (default 1)
CACHE_ON_DISK = os.getenv("BLOB_CACHE_ON_DISK", "1") == "1"


def _log(msg: str) -> None:
    print(f"[backend:init] {msg}", flush=True)


def _pick_path(*candidates: Path) -> Path | None:
    for p in candidates:
        if p and Path(p).exists():
            return Path(p)
    return None


def _blob_bytes(conn_str: str, container: str, blob_name: str) -> bytes:
    if not HAS_AZURE:
        raise RuntimeError("azure-storage-blob not installed but Blob download was requested.")
    bc = BlobClient.from_connection_string(
        conn_str=conn_str, container_name=container, blob_name=blob_name
    )
    return bc.download_blob().readall()


def _ensure_local_file(local_path: Path, blob_name: str) -> Path:
    """
    If local_path exists, return it.
    Else, download from Blob and write it to local_path (cached for next boots).
    """
    if local_path.exists():
        return local_path

    if not AZURE_CONN:
        raise FileNotFoundError(
            f"{local_path.name} not found locally and AZURE_STORAGE_CONNECTION_STRING is not set."
        )

    _log(f"Downloading '{blob_name}' from container '{AZURE_CONT}' to '{local_path}'...")
    local_path.parent.mkdir(parents=True, exist_ok=True)
    data = _blob_bytes(AZURE_CONN, AZURE_CONT, blob_name)
    with open(local_path, "wb") as f:
        f.write(data)
    _log(f"Wrote {len(data):,} bytes to {local_path}")
    return local_path


# ---------- Resolve data/model locations ----------
features_local = _pick_path(BASE_DIR / "features.csv", WWWROOT / "features.csv")
model_local    = _pick_path(BASE_DIR / "model.pkl",    WWWROOT / "model.pkl")

# Load features (CSV)
if features_local and features_local.exists():
    _log(f"Loading features from local file: {features_local}")
    df = pd.read_csv(features_local, low_memory=False)
else:
    if not AZURE_CONN:
        raise FileNotFoundError("features.csv not found and no Blob settings provided.")
    if CACHE_ON_DISK:
        features_local = _ensure_local_file(BASE_DIR / "features.csv", FEATURES_BLOB)
        _log(f"Loading features from cached file: {features_local}")
        df = pd.read_csv(features_local, low_memory=False)
    else:
        _log(f"Streaming features from Blob: {FEATURES_BLOB}")
        data = _blob_bytes(AZURE_CONN, AZURE_CONT, FEATURES_BLOB)
        df = pd.read_csv(BytesIO(data), low_memory=False)

# Load model (PKL)
if model_local and model_local.exists():
    _log(f"Loading model from local file: {model_local}")
    with open(model_local, "rb") as f:
        model = pickle.load(f)
else:
    if not AZURE_CONN:
        raise FileNotFoundError("model.pkl not found and no Blob settings provided.")
    if CACHE_ON_DISK:
        model_local = _ensure_local_file(BASE_DIR / "model.pkl", MODEL_BLOB)
        _log(f"Loading model from cached file: {model_local}")
        with open(model_local, "rb") as f:
            model = pickle.load(f)
    else:
        _log(f"Streaming model from Blob: {MODEL_BLOB}")
        data = _blob_bytes(AZURE_CONN, AZURE_CONT, MODEL_BLOB)
        model = pickle.loads(data)

# -------- Model feature metadata ----------
model_features = [
    "Lag_1", "Lag_2", "Lag_3", "Rolling_3", "Rolling_6", "Rolling_12",
    "Rolling_Trend", "Month", "Quarter", "IsYearStart", "IsYearEnd",
    "AvgPricePerBottle", "MarginRatio", "UniqueProductsSold",
    "Bottles Sold", "IsHolidayMonth",
]
category_features = [c for c in df.columns if c.endswith("_Sales") and c != "Total_Sales"]

# Make available to routes
app.config.update(
    df=df,
    model=model,
    model_features=model_features,
    category_features=category_features,
)

# Optional quick health probe
@app.get("/api/health")
def health():
    return jsonify(ok=True, rows=int(len(df)), model_loaded=bool(model_features)), 200

# ---------- Import routes robustly ----------
# ---------- Import routes robustly ----------
# right above register_routes(app)
from routes import register_routes
register_routes(app)



if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
