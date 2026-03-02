import sqlite3

conn = sqlite3.connect('sparksage.db')

print("=== TABLES ===")
cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
print([r[0] for r in cursor.fetchall()])

print("\n=== CONVERSATIONS COUNT ===")
cursor = conn.execute("SELECT COUNT(*) FROM conversations")
print(cursor.fetchone()[0])

print("\n=== ANALYTICS COUNT ===")
cursor = conn.execute("SELECT COUNT(*) FROM analytics")
print(cursor.fetchone()[0])

print("\n=== LAST 3 CONVERSATIONS ===")
cursor = conn.execute("SELECT role, content[:50], created_at FROM conversations ORDER BY rowid DESC LIMIT 3")
for r in cursor.fetchall():
    print(r)

print("\n=== ANALYTICS COLUMNS ===")
cursor = conn.execute("PRAGMA table_info(analytics)")
print([r[1] for r in cursor.fetchall()])

print("\n=== GENERAL.PY CHECK ===")
try:
    with open("cogs/general.py") as f:
        content = f.read()
    print("has add_analytics_event:", "add_analytics_event" in content)
    print("has cost_calculator:", "cost_calculator" in content)
    print("has estimate_cost:", "estimate_cost_from_text" in content)
except Exception as e:
    print("Error reading general.py:", e)

conn.close()