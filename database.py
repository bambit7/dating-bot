import sqlite3

conn = sqlite3.connect("users.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS girls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER,
    name TEXT,
    age INTEGER,
    region TEXT,
    bio TEXT,
    contact TEXT,
    photo TEXT,
    approved INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS purchases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    boy_id INTEGER,
    girl_id INTEGER
)
""")

conn.commit()
conn.close()

print("Database yaratildi!")