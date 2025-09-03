from __future__ import annotations

import os, json, logging
from typing import List, Dict, Iterable, Tuple
import pandas as pd
import joblib

# ----------------------------
# Cache / blob config
# ----------------------------
CACHE_DIR = os.environ.get("DATA_CACHE", "/home/site/data")
os.makedirs(CACHE_DIR, exist_ok=True)

FEATURES_PATH = os.path.join(CACHE_DIR, "features.csv")
MODEL_PATH    = os.path.join(CACHE_DIR, "model.pkl")
META_PATH     = os.path.join(CACHE_DIR, "artifacts.meta.json")  # stores etags

# Blob locations (env overrides optional)
ARTIFACTS_CONTAINER = os.environ.get("ARTIFACTS_CONTAINER", "artifacts")
FEATURES_BLOB_NAME  = os.environ.get("FEATURES_BLOB", "features.csv")
MODEL_BLOB_NAME     = os.environ.get("MODEL_BLOB", "model.pkl")
AZ_CONN_STR         = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")

_logger = logging.getLogger("backend.init")

def _read_meta() -> Dict[str, str]:
    try:
        with open(META_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def _write_meta(meta: Dict[str, str]) -> None:
    tmp = META_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(meta, f)
    os.replace(tmp, META_PATH)

def _get_container():
    from azure.storage.blob import BlobServiceClient
    if not AZ_CONN_STR:
        raise ValueError("AZURE_STORAGE_CONNECTION_STRING not set")
    svc = BlobServiceClient.from_connection_string(AZ_CONN_STR)
    return svc.get_container_client(ARTIFACTS_CONTAINER)

def _ensure_blob(container, blob_name: str, dest_path: str) -> str:
    """
    Ensure blob is present locally at dest_path. Uses ETag to avoid re-download.
    """
    bc = container.get_blob_client(blob_name)
    props = bc.get_blob_properties()
    etag = props.etag

    meta = _read_meta()
    if os.path.exists(dest_path) and meta.get(blob_name) == etag:
        _logger.info(f"[backend:init] Using cached {blob_name}: {dest_path}")
        return dest_path

    _logger.info(f"[backend:init] Downloading '{blob_name}' to '{dest_path}'...")
    data = bc.download_blob().readall()
    tmp = dest_path + ".downloading"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, dest_path)
    meta[blob_name] = etag
    _write_meta(meta)
    _logger.info(f"[backend:init] Wrote {len(data):,} bytes to {dest_path}")
    return dest_path

def _load_df_and_model() -> Tuple[pd.DataFrame, object]:
    """
    Download (if needed) and load artifacts, returning (df, model).
    """
    container = _get_container()
    features_file = _ensure_blob(container, FEATURES_BLOB_NAME, FEATURES_PATH)
    model_file    = _ensure_blob(container, MODEL_BLOB_NAME, MODEL_PATH)

    df = pd.read_csv(features_file)
    model = joblib.load(model_file)  # xgboost/sklearn wrapper is fine
    return df, model

def load_artifacts_into_config(cfg) -> None:
    """
    Public entry point called at app startup.
    Populates cfg['df'], cfg['model'], cfg['model_features'], cfg['category_features'].
    """
    df, model = _load_df_and_model()

    # Best-effort feature extraction; OK if empty (routes fill missing with 0s)
    model_feats: List[str] = []
    for attr in ("feature_names_in_", "get_booster"):
        if hasattr(model, attr):
            if attr == "feature_names_in_":
                try:
                    model_feats = list(getattr(model, attr))  # sklearn API
                except Exception:
                    pass
            elif attr == "get_booster":
                try:
                    booster = model.get_booster()
                    # Booster.feature_names may be None depending on how it was saved
                    if getattr(booster, "feature_names", None):
                        model_feats = list(booster.feature_names)
                except Exception:
                    pass
    cat_feats = [c for c in df.columns if c.endswith("_Sales")]

    cfg["df"] = df
    cfg["model"] = model
    cfg["model_features"] = model_feats
    cfg["category_features"] = cat_feats
    _logger.info("[backend:init] Artifacts loaded into app.config")

# ----------------------------
# Your existing helpers (unchanged)
# ----------------------------

def _ensure_required_objects(cfg) -> None:
    """
    Raise a ValueError if required objects weren't loaded into app.config.
    """
    df = cfg.get("df")
    model = cfg.get("model")
    features = cfg.get("model_features")
    if df is None or model is None or features is None:
        raise ValueError("Required objects not loaded: df, model, or model_features")
    if not isinstance(df, pd.DataFrame):
        raise ValueError("config['df'] must be a pandas DataFrame")
    if "Date" not in df.columns or "Total_Sales" not in df.columns:
        raise ValueError("DataFrame must contain 'Date' and 'Total_Sales' columns")

def _iter_unique_stores(df: pd.DataFrame) -> Iterable[Dict]:
    cols = ["Store Number", "City", "County"]
    available = [c for c in cols if c in df.columns]
    stores = (
        df[available]
        .dropna()
        .drop_duplicates()
        .sort_values("Store Number")
    )
    for _, row in stores.iterrows():
        yield {
            "store_id": int(row["Store Number"]),
            "city": str(row.get("City", "")).upper(),
            "county": str(row.get("County", "")).upper(),
        }

def _prepare_store_timeseries(df: pd.DataFrame, store_id: int, min_year: int) -> pd.DataFrame:
    store_df = df[df["Store Number"] == store_id].copy()
    if store_df.empty:
        return store_df
    store_df["Date"] = pd.to_datetime(store_df["Date"], errors="coerce")
    store_df = store_df.dropna(subset=["Date"])
    if min_year is not None:
        store_df = store_df[store_df["Date"].dt.year >= min_year]
    return store_df

def _has_min_months(store_df: pd.DataFrame, min_points: int) -> bool:
    if store_df.empty:
        return False
    monthly = (
        store_df.assign(YearMonth=store_df["Date"].dt.to_period("M").dt.to_timestamp())
        .groupby("YearMonth")["Total_Sales"]
        .sum()
    )
    return len(monthly) >= min_points

def _predict_preview(model, latest_row: pd.DataFrame, features: List[str]) -> float:
    for col in features:
        if col not in latest_row.columns:
            latest_row[col] = 0
    yhat = float(model.predict(latest_row[features])[0])
    return round(yhat, 2)
