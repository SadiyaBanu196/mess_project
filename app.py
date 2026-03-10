from flask import Flask, render_template_string, request
import sqlite3
import pickle
from datetime import datetime, time
import pytz
import os

app = Flask(__name__)
HOSTEL_CAPACITY = 250

# ---------------- TIMEZONE ---------------- #
IST = pytz.timezone("Asia/Kolkata")

# ---------------- DATABASE ---------------- #
def init_db():
    conn = sqlite3.connect("mess.db", timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    c = conn.cursor()
    # Scans table
    c.execute("""
    CREATE TABLE IF NOT EXISTS scans(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        meal TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(student_id, meal, DATE(timestamp))
    )
    """)
    # Absentees table
    c.execute("""
    CREATE TABLE IF NOT EXISTS absentees(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        from_date DATE,
        to_date DATE
    )
    """)
    # Keep DB small
    c.execute("""
    DELETE FROM scans
    WHERE timestamp < datetime('now','-7 days')
    """)
    conn.commit()
    conn.close()

init_db()

# ---------------- MODEL ---------------- #
model = pickle.load(open("model.pkl", "rb"))
print("Model expects features:", model.n_features_in_)

# Food per student (kg)
rates = {0:0.20, 1:0.30, 2:0.25}

# ---------------- MEAL DETECTION ---------------- #
def current_meal():
    now = datetime.now(IST).time()
    if time(7,0) <= now < time(10,0):
        return 0, "Breakfast"
    elif time(12,0) <= now < time(16,30):
        return 1, "Lunch"
    elif time(19,30) <= now < time(22,30):
        return 2, "Dinner"
    else:
        return None, None

# ---------------- ATTENDANCE ---------------- #
def get_today_count(meal_name):
    conn = sqlite3.connect("mess.db", timeout=10)
    c = conn.cursor()
    c.execute("""
    SELECT COUNT(*) FROM scans
    WHERE meal=? AND DATE(timestamp)=DATE('now')
    """, (meal_name,))
    count = c.fetchone()[0]
    conn.close()
    return count

def get_yesterday_meal_count(meal_name):
    conn = sqlite3.connect("mess.db", timeout=10)
    c = conn.cursor()
    c.execute("""
    SELECT COUNT(*) FROM scans
    WHERE meal=? AND DATE(timestamp)=DATE('now','-1 day')
    """, (meal_name,))
    count = c.fetchone()[0]
    conn.close()
    return count

def get_active_students():
    conn = sqlite3.connect("mess.db", timeout=10)
    c = conn.cursor()
    today = datetime.now(IST).strftime("%Y-%m-%d")
    c.execute("""
    SELECT COUNT(*) FROM absentees
    WHERE from_date <= ? AND to_date >= ?
    """, (today,today))
    absent = c.fetchone()[0]
    conn.close()
    return max(0, HOSTEL_CAPACITY - absent)

# ---------------- DASHBOARD ---------------- #
@app.route("/")
def dashboard():
    meal_index, meal_name = current_meal()
    if not meal_name:
        now = datetime.now(IST).strftime("%H:%M")
        return f"""
        <meta http-equiv="refresh" content="10">
        <h2>Smart Mess Dashboard</h2>
        <p>Current Time: {now}</p>
        <p>No active meal right now.</p>
        <p>Breakfast: 07:00–10:00</p>
        <p>Lunch: 12:00–16:30</p>
        <p>Dinner: 19:30–22:30</p>
        """

    live_count = get_today_count(meal_name)
    next_index = (meal_index + 1) % 3
    next_meal_name = ["Breakfast","Lunch","Dinner"][next_index]

    today_idx = datetime.now(IST).weekday()
    is_weekend = 1 if today_idx >= 5 else 0
    is_holiday = 1 if today_idx == 6 else 0
    day = datetime.now(IST)
    week_of_month = (day.day - 1) // 7 + 1

    # Non-veg condition
    is_nonveg_meal = 0
    if today_idx == 2 and next_index == 2 and week_of_month in [2,4]:
        is_nonveg_meal = 1

    prev_count = live_count if live_count > 0 else get_yesterday_meal_count(next_meal_name)

    features_next = [[
        is_holiday,
        is_weekend,
        is_nonveg_meal,
        week_of_month,
        prev_count,
        next_index,
        today_idx
    ]]

    predicted_next = int(model.predict(features_next)[0])

    # Safety caps
    if live_count < 20:
        predicted_next = min(predicted_next, int(HOSTEL_CAPACITY * 0.6))
    if live_count < 30:
        predicted_next = live_count * 2

    population_ratio = live_count / HOSTEL_CAPACITY if HOSTEL_CAPACITY else 1
    if live_count > 60 and population_ratio < 0.35:
        predicted_next = int(predicted_next * population_ratio * 3)
    if live_count > 20:
        predicted_next = int((predicted_next + live_count) / 2)

    active_students = get_active_students()
    predicted_next = max(10, min(predicted_next, active_students))
    food_next = round(predicted_next * rates[next_index], 2)

    return render_template_string("""
    <meta http-equiv="refresh" content="5">
    <h2>Smart Mess Dashboard</h2>
    <h3>Current Meal: {{meal_name}}</h3>
    <p>Hostel Capacity: {{capacity}}</p>
    <p>Active Hostel Students: {{active_students}}</p>
    <p>Live Attendance: {{live_count}}</p>
    <p>Day: {{today}}</p>
    <hr>
    <h3>Next Meal Prediction</h3>
    <p>Meal: {{next_meal_name}}</p>
    <p>Predicted Students: {{predicted_next}}</p>
    <p>Food to Cook (kg): {{food_next}}</p>
    <p>Calculation: {{predicted_next}} students × {{rate}} kg</p>
    <hr>
    <a href="/scan">Open Scanner</a><br>
    <a href="/logs">View Scan Logs</a>
    """,
    meal_name=meal_name,
    live_count=live_count,
    today=datetime.now(IST).strftime("%A"),
    next_meal_name=next_meal_name,
    predicted_next=predicted_next,
    food_next=food_next,
    capacity=HOSTEL_CAPACITY,
    active_students=active_students,
    rate=rates[next_index]
    )

# ---------------- SCANNER ---------------- #
@app.route("/scan", methods=["GET","POST"])
def scan():
    meal_index, meal_name = current_meal()
    if not meal_name:
        return "Scanning allowed only during meal hours."

    if request.method == "POST":
        student_id = request.form.get("student_id")
        action = request.form.get("action")
        from_date = request.form.get("from_date")
        to_date = request.form.get("to_date")

        if not student_id or not action:
            return "Student ID and action required."

        if action == "in":
            conn = sqlite3.connect("mess.db", timeout=10)
            c = conn.cursor()
            try:
                c.execute("INSERT INTO scans(student_id, meal) VALUES(?, ?)", (student_id, meal_name))
                conn.commit()
                message = f"Scan successful for {student_id}!"
            except sqlite3.IntegrityError:
                message = f"Already scanned for {meal_name}!"
            conn.close()
        elif action == "leave":
            # default to today if no dates
            if not from_date: from_date = datetime.now(IST).strftime("%Y-%m-%d")
            if not to_date: to_date = datetime.now(IST).strftime("%Y-%m-%d")
            conn = sqlite3.connect("mess.db", timeout=10)
            c = conn.cursor()
            c.execute("""
                INSERT OR IGNORE INTO absentees(student_id, from_date, to_date)
                VALUES(?, ?, ?)
            """, (student_id, from_date, to_date))
            conn.commit()
            conn.close()
            message = f"Leave marked for {student_id} from {from_date} to {to_date}!"
        else:
            return "Invalid action."

        active_students = get_active_students()
        # simple next meal prediction
        next_index = ["Breakfast","Lunch","Dinner"].index(meal_name)
        features_next = [[0,0,0,0,get_today_count(meal_name),next_index,datetime.now(IST).weekday()]]
        next_meal_count = int(model.predict(features_next)[0])
        next_meal_count = max(10, min(next_meal_count, active_students))

        return f"{message} <br>Active Students: {active_students} <br>Predicted Next Meal: {next_meal_count} <br><a href='/scan'>Next Student</a>"

    return """
    <h2>Smart Mess Scanner</h2>
    <form method="POST">
    Student ID:<br>
    <input type="text" name="student_id" required><br><br>
    
    Action:<br>
    <select name="action">
        <option value="in">Scan Attendance</option>
        <option value="leave">Mark Leave</option>
    </select><br><br>
    Leave From (for multi-day leave):<br>
    <input type="date" name="from_date"><br><br>
    Leave To:<br>
    <input type="date" name="to_date"><br><br>
    <button type="submit">Submit</button>
    </form>
    <br>
    <a href="/">Back to Dashboard</a>
    """

# ---------------- LOGS ---------------- #
@app.route("/logs")
def logs():
    conn = sqlite3.connect("mess.db", timeout=10)
    c = conn.cursor()
    c.execute("""
    SELECT student_id, meal, timestamp
    FROM scans
    ORDER BY timestamp DESC
    LIMIT 50
    """)
    rows = c.fetchall()
    conn.close()
    html = "<h2>Recent Scans</h2><table border=1>"
    html += "<tr><th>Student</th><th>Meal</th><th>Time</th></tr>"
    for r in rows:
        html += f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td></tr>"
    html += "</table><br><a href='/'>Back to Dashboard</a>"
    return html

# ---------------- RUN ---------------- #
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)