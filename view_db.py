import sqlite3

conn = sqlite3.connect("speech.db")
cursor = conn.cursor()

cursor.execute("SELECT * FROM reports")
rows = cursor.fetchall()

for row in rows:
    print(row)

conn.close()