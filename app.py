from flask import Flask, render_template, request, session
import sqlite3
import pickle
from datetime import datetime, time, timedelta
import pytz
import os

app = Flask(__name__)
app.secret_key = "supersecretkey"  # Needed for session

HOSTEL_CAPACITY = 250
IST = pytz.timezone("Asia/Kolkata")

# ---------------- DATABASE ---------------- #

def init_db():
    conn = sqlite3.connect("mess.db", timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS scans(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        meal TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(student_id, meal, DATE(timestamp))
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS absentees(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        from_date DATE,
        to_date DATE
    )
    """)

    c.execute("""
    DELETE FROM scans
    WHERE timestamp < datetime('now','-7 days')
    """)

    conn.commit()
    conn.close()

init_db()

# ---------------- MODEL ---------------- #

model = pickle.load(open(os.path.join(os.getcwd(),"model.pkl"), "rb"))
print("Model expects features:", model.n_features_in_)

# ---------------- FOOD PORTIONS ---------------- #

breakfast_menu = {
    "idli": {"portion":3, "unit":"pieces"},
    "dosa": {"portion":3, "unit":"pieces"},
    "chapati": {"portion":3, "unit":"pieces"},
    "puri": {"portion":3, "unit":"pieces"},
    "upma": {"portion":0.063, "unit":"kg rava"},
    "pongal": {"portion":0.08, "unit":"kg rice"}
}

RICE_PER_STUDENT = 0.12

# ---------------- MEAL DETECTION ---------------- #

def current_meal():
    now = datetime.now(IST).time()
    if time(7,0) <= now < time(12,0):
        return 0, "Breakfast"
    elif time(12,0) <= now < time(16,30):
        return 1, "Lunch"
    elif time(19,30) <= now < time(23,30):
        return 2, "Dinner"
    else:
        return None, None

# ---------------- ATTENDANCE ---------------- #

def get_today_count(meal_name):
    conn = sqlite3.connect("mess.db", timeout=10)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM scans WHERE meal=? AND DATE(timestamp)=DATE('now')",(meal_name,))
    count = c.fetchone()[0]
    conn.close()
    return count

def get_yesterday_meal_count(meal_name):
    conn = sqlite3.connect("mess.db", timeout=10)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM scans WHERE meal=? AND DATE(timestamp)=DATE('now','-1 day')",(meal_name,))
    count = c.fetchone()[0]
    conn.close()
    return count

def get_active_students():
    conn = sqlite3.connect("mess.db", timeout=10)
    c = conn.cursor()
    today = datetime.now(IST).strftime("%Y-%m-%d")
    c.execute("SELECT COUNT(*) FROM absentees WHERE from_date <= ? AND to_date >= ?", (today,today))
    absent = c.fetchone()[0]
    conn.close()
    return max(0, HOSTEL_CAPACITY - absent)

# ---------------- DASHBOARD ---------------- #

@app.route("/", methods=["GET","POST"])
def dashboard():
    meal_index, meal_name = current_meal()
    if not meal_name:
        now = datetime.now(IST).strftime("%H:%M")
        return f"""
        <meta http-equiv="refresh" content="10">
        <h2>Smart Mess Dashboard</h2>
        <p>Current Time: {now}</p>
        <p>No active meal right now.</p>
        """

    live_count = get_today_count(meal_name)
    next_index = (meal_index + 1) % 3
    next_meal_name = ["Breakfast","Lunch","Dinner"][next_index]
    today_idx = datetime.now(IST).weekday()
    is_weekend = 1 if today_idx >= 5 else 0
    is_holiday = 1 if today_idx == 6 else 0
    day = datetime.now(IST)
    week_of_month = (day.day - 1)//7 + 1

    is_nonveg_meal = 0
    if today_idx == 2 and next_index == 2 and week_of_month in [2,4]:
        is_nonveg_meal = 1

    prev_count = live_count if live_count > 0 else get_yesterday_meal_count(next_meal_name)
    features_next = [[is_holiday, is_weekend, is_nonveg_meal, week_of_month, prev_count, next_index, today_idx]]
    predicted_next = int(model.predict(features_next)[0])

    # Stabilization
    if live_count < 20:
        predicted_next = min(predicted_next, int(HOSTEL_CAPACITY * 0.6))
    if live_count < 30:
        predicted_next = live_count * 2
    population_ratio = live_count / HOSTEL_CAPACITY if HOSTEL_CAPACITY else 1
    if live_count > 60 and population_ratio < 0.35:
        predicted_next = int(predicted_next * population_ratio * 3)
    if live_count > 20:
        predicted_next = int((predicted_next + live_count)/2)

    active_students = get_active_students()
    predicted_next = max(10, min(predicted_next, active_students))

    # -------- Persist menu selection ----------
    if request.method == "POST":
        menu = request.form.get("menu", "idli")
        session['menu'] = menu
    else:
        menu = session.get("menu", "idli")

    # Food calculation
    food_text = ""
    if next_meal_name == "Breakfast" and menu in breakfast_menu:
        portion = breakfast_menu[menu]["portion"]
        unit = breakfast_menu[menu]["unit"]
        total_food = round(predicted_next * portion,2)
        food_text = f"{menu.title()} required: {total_food} {unit}"
    elif next_meal_name != "Breakfast":
        rice_required = round(predicted_next * RICE_PER_STUDENT,2)
        food_text = f"Rice required: {rice_required} kg"

    return render_template(
    "dashboard.html",
    meal_name=meal_name,
    next_meal_name=next_meal_name,
    live_count=live_count,
    predicted_next=predicted_next,
    capacity=HOSTEL_CAPACITY,
    active_students=active_students,
    food_text=food_text,
    menu=menu,
    menu_list=list(breakfast_menu.keys()))

# ---------------- SCANNER ---------------- #

@app.route("/scan", methods=["GET","POST"])
def scan():
    meal_index, meal_name = current_meal()
    if not meal_name:
        return "Scanning allowed only during meal hours."

    if request.method == "POST":
        student_id = request.form.get("student_id")
        conn = sqlite3.connect("mess.db", timeout=10)
        c = conn.cursor()
        try:
            c.execute("INSERT INTO scans(student_id, meal) VALUES(?,?)",(student_id,meal_name))
            conn.commit()
            message = "Scan successful"
        except:
            message = "Already scanned!"
        conn.close()
        return message + "<br><a href='/scan'>Next student</a>"

    return render_template("scan.html")

# ---------------- LEAVE ---------------- #

@app.route("/leave", methods=["GET","POST"])
def leave():
    if request.method == "POST":
        student_id = request.form.get("student_id")
        from_date = request.form.get("from_date")
        to_date = request.form.get("to_date")

        conn = sqlite3.connect("mess.db", timeout=10)
        c = conn.cursor()

        # Prevent overlapping leaves
        c.execute("SELECT * FROM absentees WHERE student_id=? AND to_date >= ?", (student_id, from_date))
        existing = c.fetchone()
        if existing:
            conn.close()
            return "Leave already active<br><a href='/leave'>Next</a>"

        c.execute("INSERT INTO absentees(student_id, from_date, to_date) VALUES(?,?,?)", (student_id, from_date, to_date))
        conn.commit()
        conn.close()
        return f"Leave marked from {from_date} to {to_date}<br><a href='/leave'>Next</a>"

    return render_template("leave.html")

# ---------------- LOGS ---------------- #

@app.route("/logs")
def logs():
    conn = sqlite3.connect("mess.db", timeout=10)
    c = conn.cursor()
    c.execute("SELECT student_id, meal, timestamp FROM scans ORDER BY timestamp DESC LIMIT 50")
    rows = c.fetchall()
    conn.close()
    return render_template("logs.html", rows=rows)

# ---------------- RUN ---------------- #

if __name__ == "__main__":
    port = int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0", port=port)