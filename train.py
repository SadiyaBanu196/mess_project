import pandas as pd
import sqlite3
import pickle
from sklearn.ensemble import RandomForestRegressor

conn = sqlite3.connect("mess.db")
df = pd.read_sql("SELECT * FROM meal_counts", conn)

df['prev_count'] = df['student_count'].shift(1)
df.dropna(inplace=True)

X = df[['is_holiday','prev_count','meal_index','day_of_week']]
y = df['student_count']

model = RandomForestRegressor(n_estimators=200)
model.fit(X, y)

pickle.dump(model, open("model.pkl","wb"))

print("Model trained successfully")