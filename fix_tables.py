import sqlite3

conn = sqlite3.connect('sparksage.db')

# Drop and recreate with correct column name (created_at)
conn.execute("DROP TABLE IF EXISTS member_events")
conn.execute("DROP TABLE IF EXISTS member_messages")

conn.execute('''CREATE TABLE member_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    username TEXT,
    event_type TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
)''')

conn.execute('''CREATE TABLE member_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    username TEXT,
    channel_id TEXT,
    hour INTEGER,
    created_at TEXT DEFAULT (datetime('now'))
)''')

conn.commit()
conn.close()
print('Tables recreated successfully with correct columns!')