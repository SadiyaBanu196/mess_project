import sqlite3
import random
from datetime import datetime, timedelta

conn = sqlite3.connect("mess.db")
cur = conn.cursor()

cur.execute("""
CREATE TABLE meal_counts(
    day_of_week INTEGER,
    is_holiday INTEGER,
    meal_index INTEGER,
    student_count INTEGER
)
""")

start = datetime(2026,1,1)

for i in range(120):  # 40 days * 3 meals
    day = start + timedelta(days=i//3)

    dow = day.weekday()          # integer 0–6
    meal = i % 3
    holiday = 1 if dow == 6 else 0

    base = 220
    noise = random.randint(-20,20)

    count = base + noise - (10 if meal==2 else 0)

    cur.execute("INSERT INTO meal_counts VALUES (?,?,?,?)",
                (dow, holiday, meal, count))

conn.commit()
conn.close()

print("Fresh DB created")