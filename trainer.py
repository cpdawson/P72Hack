import pandas as pd
import numpy as np
import joblib
from datetime import datetime
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.preprocessing import OneHotEncoder
from sklearn.model_selection import train_test_split

# Load your raw traffic data CSV
df = pd.read_csv("cleaned_data.csv", sep=",")  # or comma if it's CSV

# Clean and convert columns
df["Datetime"] = pd.to_datetime(df["Datetime"])
df["CRZ Entries"] = pd.to_numeric(df["CRZ Entries"], errors="coerce")
df = df.dropna(subset=["CRZ Entries"])

# Extract features from datetime
df["hour"] = df["Datetime"].dt.hour
df["day_of_week"] = df["Datetime"].dt.weekday
df["month"] = df["Datetime"].dt.month
df["is_weekend"] = df["day_of_week"].isin([5, 6]).astype(int)
df["date_str"] = df["Datetime"].dt.strftime("%Y-%m-%d")

# Aggregate into 1-hour blocks per day/location/class
agg_df = df.groupby(["date_str", "hour", "Vehicle Class", "Detection Group", "is_weekend", "month", "day_of_week"]).agg({
    "CRZ Entries": "sum"
}).reset_index()

# Create price lookup (you can customize these)
PRICE_MAP = {
    ('Car', 0): 2.25,
    ('Car', 1): 9,
    ('Buses', 0): 3.6,
    ('Buses', 1): 14.4,
    ('Motorcycles', 0): 1.05,
    ('Motorcycles', 1): 4.5,
    ('Taxi', 0): 0.75,
    ('Taxi', 1): 0.75,
    ('Single Unit Trucks', 0): 3.6,
    ('Single Unit Trucks', 1): 14.4,
    ('Multi Unit Trucks', 0): 5.40,
    ('Multi Unit Trucks', 1): 21.60
}

# Create is_peak column for pricing
agg_df["is_peak"] = agg_df["hour"].between(5, 21)
agg_df["is_peak"] = agg_df["is_peak"].astype(int)

# Apply price per class
agg_df["price_per"] = agg_df.apply(
    lambda row: PRICE_MAP.get((row["Vehicle Class"], row["is_peak"]), 3),
    axis=1
)
agg_df["revenue"] = agg_df["CRZ Entries"] * agg_df["price_per"]

# Define features and labels
X = agg_df[["hour", "day_of_week", "month", "is_weekend", "Vehicle Class", "Detection Group"]]
y_vehicles = agg_df["CRZ Entries"]
y_revenue = agg_df["revenue"]

# One-hot encode categorical vars
encoder = OneHotEncoder(sparse_output=False)
X_encoded = encoder.fit_transform(X)

# Train two models: one for vehicle count, one for revenue
X_train, X_test, yv_train, yv_test, yr_train, yr_test = train_test_split(
    X_encoded, y_vehicles, y_revenue, test_size=0.2, random_state=42
)

vehicle_model = GradientBoostingRegressor()
vehicle_model.fit(X_train, yv_train)

revenue_model = GradientBoostingRegressor()
revenue_model.fit(X_train, yr_train)

# Save models and encoder
joblib.dump(vehicle_model, "vehicle_model.pkl")
joblib.dump(revenue_model, "revenue_model.pkl")
joblib.dump(encoder, "filter_encoder.pkl")

print("Models trained and saved: vehicle_model.pkl, revenue_model.pkl, filter_encoder.pkl")
