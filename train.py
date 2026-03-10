import pandas as pd
import sqlite3
import pickle
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score

DB_PATH = "mess.db"
MODEL_PATH = "model.pkl"

# -----------------------

# Load Data

# -----------------------

conn = sqlite3.connect(DB_PATH)
df = pd.read_sql("SELECT * FROM meal_counts", conn)
conn.close()

if df.empty:
    raise ValueError("meal_counts table is empty. Add historical data before training.")

required_cols = {
"date",
"meal_index",
"student_count",
"day_of_week",
"is_holiday",
"is_weekend",
"is_nonveg_meal",
"week_of_month"
}
missing = required_cols - set(df.columns)
if missing:
    raise ValueError(f"Missing columns in meal_counts: {missing}")
df["day_of_week"] = df["day_of_week"].astype(int)
df["meal_index"] = df["meal_index"].astype(int)
df["is_holiday"] = df["is_holiday"].astype(int)
df["is_weekend"] = df["is_weekend"].astype(int)
df["is_nonveg_meal"] = df["is_nonveg_meal"].astype(int)
df["week_of_month"] = df["week_of_month"].astype(int)
df["student_count"] = pd.to_numeric(df["student_count"], errors="coerce")
df = df.dropna(subset=["student_count"])
df = df[(df["student_count"] >= 0) & (df["student_count"] <= 300)]
print("Rows loaded:", len(df))
if len(df) == 0:
    raise ValueError("No valid rows after cleaning student_count.")
# -----------------------

# Prepare Dataset

# -----------------------

df["date"] = pd.to_datetime(df["date"])

# sort chronologically

df = df.sort_values(by=["date","meal_index"])
df = df.reset_index(drop=True)
# previous meal attendance
df["prev_count"] = df.groupby("date")["student_count"].shift(1)

df["prev_count"] = df["prev_count"].fillna(
    df.groupby("meal_index")["student_count"].transform("mean"))
df["prev_count"] = pd.to_numeric(df["prev_count"])
if len(df) < 10:
    raise ValueError("Not enough data to train. Add more historical rows.")

print("\nTraining data preview:")
print(df.head())

X = df[
[
"is_holiday",
"is_weekend",
"is_nonveg_meal",
"week_of_month",
"prev_count",
"meal_index",
"day_of_week"
]
]
X = X.apply(pd.to_numeric)

y = df["student_count"]

#-----------------------
#Train / Validation Split
#-----------------------

X_train, X_test, y_train, y_test = train_test_split(
X, y, test_size=0.2, random_state=42
)


# -----------------------

# Train Model

# -----------------------

model = RandomForestRegressor(
n_estimators=200,
random_state=42,
n_jobs=-1
)

model.fit(X_train, y_train)
preds = model.predict(X_test)
print("Training R2 Score:", r2_score(y_test, preds))

importances = model.feature_importances_
features = X.columns

print("\nFeature Importance:")
for f, imp in zip(features, importances):
    print(f"{f}: {imp:.3f}")

# -----------------------

# Save Model

# -----------------------

with open(MODEL_PATH, "wb") as f:
    pickle.dump(model, f)

print("Model trained successfully.")
print(f"Training rows used: {len(df)}")
print("Model saved to model.pkl")
