from flask import Flask, render_template_string, request
import sqlite3
import pickle
from datetime import datetime, time

app = Flask(__name__)

# Initialize DB
def init_db():
    conn = sqlite3.connect("mess.db")
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS scans(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        meal TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    conn.commit()
    conn.close()

init_db()

# Load ML model
model = pickle.load(open("model.pkl", "rb"))

# Food rate per student (kgs)
rates = {0:0.35, 1:0.45, 2:0.40}  # Breakfast, Lunch, Dinner

# Determine current meal
def current_meal():
    now = datetime.now().time()
    if time(7,0) <= now <= time(10,0):
        return 0, "Breakfast"
    elif time(12,0) <= now <= time(16,0):
        return 1, "Lunch"
    elif time(19,30) <= now <= time(22,0):
        return 2, "Dinner"
    else:
        return None, None

# Get last recorded attendance for a meal
def get_last_count(meal_name):
    if not meal_name:
        return 0
    conn = sqlite3.connect("mess.db")
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM scans WHERE meal=? AND DATE(timestamp)=DATE('now')", (meal_name,))
    last_count = c.fetchone()[0]
    conn.close()
    return last_count

# Dashboard route
@app.route("/")
def dashboard():
    meal_index, meal_name = current_meal()
    if not meal_name:
        return "<h2>No active meal now!</h2>"

    # Last actual attendance for current meal
    last_count = get_last_count(meal_name)

    # Predict next meal (look-ahead)
    next_index = (meal_index + 1) % 3  # 0→1→2→0
    next_meal_name = ["Breakfast", "Lunch", "Dinner"][next_index]
    today = datetime.now().weekday()
    features_next = [[0, last_count, next_index, today]]
    predicted_next = int(model.predict(features_next)[0])
    food_next = round(predicted_next * rates[next_index], 2)

    # Render dashboard
    return render_template_string("""
        <h2>Smart Mess Dashboard</h2>
        <h3>Current Meal: {{ meal_name }}</h3>
        <p>Last Recorded Attendance: {{ last_count }}</p>
        <hr>
        <h3>Next Meal Prediction</h3>
        <p>Meal: {{ next_meal_name }}</p>
        <p>Predicted Students: {{ predicted_next }}</p>
        <p>Food to Cook (kg): {{ food_next }}</p>
    """,
    meal_name=meal_name,
    last_count=last_count,
    next_meal_name=next_meal_name,
    predicted_next=predicted_next,
    food_next=food_next
    )

# QR Scan endpoint
@app.route("/scan", methods=["GET", "POST"])
def scan():
    meal_index, meal_name = current_meal()
    if not meal_name:
        return "Scanning allowed only during meal hours!", 400

    student_id = request.args.get("id", "0")
    conn = sqlite3.connect("mess.db")
    c = conn.cursor()
    c.execute("INSERT INTO scans(meal) VALUES(?)", (meal_name,))
    conn.commit()
    conn.close()
    return f"Attendance Recorded for {meal_name}, Student ID: {student_id}."

import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)