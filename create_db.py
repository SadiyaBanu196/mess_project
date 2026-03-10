import sqlite3
import random
from datetime import datetime, timedelta

conn = sqlite3.connect("mess.db")
cur = conn.cursor()

# reset table

cur.execute("DROP TABLE IF EXISTS meal_counts")

cur.execute("""
CREATE TABLE meal_counts(
date TEXT,
day_of_week INTEGER,
is_holiday INTEGER,
meal_index INTEGER,
is_weekend INTEGER,
is_nonveg_meal INTEGER,
week_of_month INTEGER,
student_count INTEGER
)
""")
# Table for students on leave
cur.execute("""
CREATE TABLE IF NOT EXISTS absentees(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT,
    from_date DATE,
    to_date DATE
)
""")

start = datetime(2025, 1, 1)

for d in range(365):  # 365 days


    day = start + timedelta(days=d)
    date_str = day.strftime("%Y-%m-%d")

    dow = day.weekday()

    is_weekend = 1 if dow >= 5 else 0
    week_of_month = (day.day - 1) // 7 + 1
    is_holiday = 1 if dow == 6 else 0

    for meal in range(3):  # breakfast, lunch, dinner

        base = 230

        # weekday pattern
        if dow == 0:
            base += 15
        if dow == 5:
            base -= 5
        if dow == 6:
            base -= 40

        # meal pattern
        if meal == 0:
            base -= 15
        if meal == 2:
            base -= 20

        # holiday effect
        if is_holiday:
            base -= 30

        # non-veg Wednesday dinner twice a month
        is_nonveg_meal = 0
        if dow == 2 and meal == 2:
            if random.random() < 0.5:
                is_nonveg_meal = 1
                base += 25

        noise = random.randint(-5, 5)

        student_count = base + noise

        cur.execute(
            "INSERT INTO meal_counts VALUES (?,?,?,?,?,?,?,?)",
            (
                date_str,
                dow,
                is_holiday,
                meal,
                is_weekend,
                is_nonveg_meal,
                week_of_month,
                student_count
            )
        )
    

conn.commit()
conn.close()

print("Fresh DB created")
