import sqlite3

def init_db():
    conn = sqlite3.connect("mess.db")
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS scans(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        meal TEXT,
        time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()