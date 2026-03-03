import sqlite3
import random
from datetime import datetime, timedelta

conn = sqlite3.connect("mess.db")
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS meal_counts(
date TEXT,
meal_type TEXT,
meal_index INTEGER,
day_of_week TEXT,
is_holiday INTEGER,
prev_meal_count INTEGER,
student_count INTEGER
)
""")

start = datetime(2026,1,1)
prev = 180

for i in range(40):
    d = start + timedelta(days=i)
    day = d.strftime("%A")
    holiday = 1 if day=="Sunday" else 0

    for meal, base,idx in [("breakfast",220,0),("lunch",210,1),("dinner",200,2)]:
        count = base + random.randint(-20,20)
        if holiday:
            count -= 60

        c.execute("INSERT INTO meal_counts VALUES (?,?,?,?,?,?,?)",
          (str(d.date()), meal, idx, day, holiday, prev, count))

        prev = count

conn.commit()
conn.close()

print("DB ready")