from __future__ import annotations

from typing import List, Dict, Iterable
import pandas as pd

# ----------------------------
# Helpers
# ----------------------------


# ----------------------------
# Validates that all required objects for the app exist and are correctly formatted.
# Input:
#   - cfg: A Flask config object (dictionary-like) that holds app-wide data and settings
#
# Returns:
#   - None (raises ValueError if validation fails)
#
# Details:
#   1. Retrieve `df`, `model`, and `model_features` from the config.
#   2. If any are missing (None), raise a ValueError.
#   3. Verify that `df` is a Pandas DataFrame.
#   4. Ensure that the DataFrame contains the required columns: "Date" and "Total_Sales".
#   5. If any check fails, stop execution by raising a ValueError with a descriptive message.
# ----------------------------
def _ensure_required_objects(cfg) -> None:  # cfg is a box holding all your app’s important objects so you can check them in one place
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


# ----------------------------
# Input: Pandas DataFrame containing store data
# Returns: An iterable (generator) that yields one dictionary per unique store.
#          Instead of building a full list of stores in memory, it produces them
#          one at a time as you loop through, keeping memory use low and allowing
#          processing to begin immediately.
#
# 1. Define the target columns we care about: "Store Number", "City", "County"
# 2. Check which of those target columns actually exist in the DataFrame
# 3. Create a smaller DataFrame with only available columns
# 4. Remove rows with missing values in those columns
# 5. Remove duplicate store entries so each store appears once
# 6. Sort the stores by "Store Number" in ascending order
# 7. Loop through each row and yield a dictionary:
#    - store_id: int version of "Store Number"
#    - city: uppercase string of "City"
#    - county: uppercase string of "County"
# ----------------------------
def _iter_unique_stores(df: pd.DataFrame) -> Iterable[Dict]:
    """
    Yield unique store records with basic identity fields.
    """
    cols = ["Store Number", "City", "County"]  # List of columns we want
    available = [c for c in cols if c in df.columns]  # Filtered list of only those columns that exist in df
    stores = (  # Building a clean store list
        df[available]  # Take only the relevant columns we found
        .dropna()  # Remove rows that are missing values
        .drop_duplicates()  # Remove duplicates
        .sort_values("Store Number")  # Sort the store in ascending order
    )
    for _, row in stores.iterrows():  # Loops through the DataFrame row by row
        yield {  # yield is like return, but instead of ending the function, it pauses it so it can produce multiple results over time.
            "store_id": int(row["Store Number"]),  # Convert store_id to int
            "city": str(row.get("City", "")).upper(),  # Convert city to string
            "county": str(row.get("County", "")).upper(),  # Convert country to string
        }


# ----------------------------
# Allows the caller to filter the DataFrame for a specific store and minimum year.
# Input:
#   - df (Pandas DataFrame): The complete dataset containing sales data for all stores
#   - store_id (int): The store number to filter for
#   - min_year (int): The earliest year of sales data to include
#
# Returns:
#   - A new Pandas DataFrame containing only rows for the specified store
#     and only dates on or after the given min_year.
#
# Details:
#   1. Select only rows where "Store Number" matches the given store_id.
#   2. Convert the "Date" column to proper datetime objects for safe filtering.
#   3. Drop any rows where "Date" could not be parsed.
#   4. If a min_year is provided, filter out all rows before that year.
#   5. Return the cleaned, filtered DataFrame for further processing.
#
# ----------------------------
def _prepare_store_timeseries(
    df: pd.DataFrame,
    store_id: int,
    min_year: int,
) -> pd.DataFrame:
    """
    Return the per-row store dataframe filtered to min_year+ and with Date parsed.
    """
    store_df = df[df["Store Number"] == store_id].copy()  # Take only the rows from the master dataset where the store number equals the store_id we’re looking for, and work with a separate copy of that data.
    if store_df.empty:  # If our filtered DataFrame is empty, it means there were no matching rows, return the dataframe
        return store_df
    store_df["Date"] = pd.to_datetime(store_df["Date"], errors="coerce")  # Convert the "Date" column to proper datetime objects for safe filtering.
    store_df = store_df.dropna(subset=["Date"])
    if min_year is not None:
        store_df = store_df[store_df["Date"].dt.year >= min_year]
    return store_df


# ----------------------------
# Checks whether a store has sales data for at least a given number of unique months.
# Input:
#   - store_df (Pandas DataFrame): Sales data for a single store
#   - min_points (int): The minimum number of distinct months required
#
# Returns:
#   - True if the store has sales data for at least `min_points` unique months,
#     otherwise False.
#
# Details:
#   1. If the DataFrame is empty, return False immediately.
#   2. Create a new "YearMonth" column by converting the "Date" column to
#      year-month periods and back to timestamps representing the first day
#      of that month.
#   3. Group the data by "YearMonth" and sum the "Total_Sales" for each month.
#   4. Count the number of unique months and compare it to `min_points`.
#   5. Return True if the count is greater than or equal to `min_points`,
#      otherwise False.
# ----------------------------
def _has_min_months(store_df: pd.DataFrame, min_points: int) -> bool:
    """
    Check if a store has at least `min_points` monthly aggregates since the cutoff.
    """
    if store_df.empty:  # If the DataFrame is empty (no rows for that store), the store clearly doesn’t have enough months of data, so it returns False immediately
        return False
    monthly = (
        store_df.assign(YearMonth=store_df["Date"].dt.to_period("M").dt.to_timestamp())  # This creates a new column called YearMonth without overwriting the original DataFrame.
        # .dt.to_period("M") turns the full date into just the year-month period (e.g., 2024-05-15 → 2024-05).
        # .dt.to_timestamp() converts that back into a normal datetime at the start of that month (2024-05-01).

        # So now YearMonth contains the month each row belongs to.
        # Date                          Total_Sales             YearMonth
        # 2024-01-15                     1500.00                2024-01-01
        # 2024-01-28                     2000.00                2024-01-01
        # 2024-02-02                     2500.00                2024-02-01
        .groupby("YearMonth")["Total_Sales"]  # Groups all rows for the same month together.
        .sum()  # Sums Total_Sales for that month so each month is a single value.
    )
    return len(monthly) >= min_points
    # monthly here is a Pandas Series where the index is YearMonth.
    # len(monthly) tells us how many unique months have sales data.
    # If that count is greater than or equal to the required min_points (e.g., 5 months), return True; otherwise False.


# ----------------------------
# Generates a single forecast value using the most recent store data row.
# Input:
#   - model: A trained machine learning model with a .predict() method
#   - latest_row (Pandas DataFrame): A single-row DataFrame containing the most
#       recent data for the store
#   - features (List[str]): The list of feature column names expected by the model
#
# Returns:
#   - float: The predicted value (rounded to 2 decimal places) for the given row
#
# Details:
#   1. Loop through each feature in the `features` list.
#   2. If a feature column is missing from `latest_row`, add it and fill with 0.
#   3. Select only the feature columns from `latest_row` in the correct order.
#   4. Call `model.predict()` on this row to generate the forecast.
#   5. Convert the prediction to a Python float, round to 2 decimals, and return it.
# ----------------------------
def _predict_preview(
    model,
    latest_row: pd.DataFrame,
    features: List[str],
) -> float:
    """
    Predict a single-step preview from the latest available row.
    Missing features are filled with 0.
    """
    for col in features:
        if col not in latest_row.columns:
            latest_row[col] = 0
    # latest_row[features] → selects only the columns the model was trained with, in the right order.
    # model.predict(...) → returns a NumPy array of predictions (even though we only gave it one row).
    # [0] → takes the first prediction from that array.
    # float(...) → converts from NumPy float to a standard Python float.
    yhat = float(model.predict(latest_row[features])[0])
    return round(yhat, 2)
