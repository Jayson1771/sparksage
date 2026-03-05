import sqlite3

conn = sqlite3.connect('sparksage.db')

conn.execute('''CREATE TABLE IF NOT EXISTS member_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    username TEXT,
    event_type TEXT NOT NULL,
    timestamp TEXT DEFAULT (datetime('now'))
)''')

conn.execute('''CREATE TABLE IF NOT EXISTS member_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    username TEXT,
    channel_id TEXT,
    timestamp TEXT DEFAULT (datetime('now'))
)''')

conn.commit()
conn.close()
print('Tables created successfully!')