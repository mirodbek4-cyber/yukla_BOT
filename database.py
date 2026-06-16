import sqlite3

class Database:
    def __init__(self, db_file="bot_database.db"):
        self.conn = sqlite3.connect(db_file, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        # Foydalanuvchilar jadvali
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                status TEXT DEFAULT 'active'
            )
        """)
        # Majburiy obuna kanallari jadvali
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                channel_id TEXT PRIMARY KEY,
                invite_link TEXT,
                is_mandatory INTEGER DEFAULT 1
            )
        """)
        self.conn.commit()

    # Foydalanuvchi qo'shish
    def add_user(self, user_id):
        try:
            self.cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
            self.conn.commit()
        except Exception as e:
            print(f"DB Error: {e}")

    # Statisika olish
    def get_stats(self):
        all_users = self.cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        blocked_users = self.cursor.execute("SELECT COUNT(*) FROM users WHERE status='blocked'").fetchone()[0]
        return {"all": all_users, "blocked": blocked_users}

    def get_all_users(self):
        return [row[0] for row in self.cursor.execute("SELECT user_id FROM users").fetchall()]

    def set_user_status(self, user_id, status):
        self.cursor.execute("UPDATE users SET status=? WHERE user_id=?", (status, user_id))
        self.conn.commit()

    # Kanallar bilan ishlash
    def add_channel(self, channel_id, invite_link, is_mandatory=1):
        self.cursor.execute("INSERT OR REPLACE INTO channels (channel_id, invite_link, is_mandatory) VALUES (?, ?, ?)",
                            (channel_id, invite_link, is_mandatory))
        self.conn.commit()

    def remove_channel(self, channel_id):
        self.cursor.execute("DELETE FROM channels WHERE channel_id=?", (channel_id,))
        self.conn.commit()

    def get_channels(self):
        self.cursor.execute("SELECT channel_id, invite_link, is_mandatory FROM channels")
        return self.cursor.fetchall()

db = Database()