import logging
import sqlite3
from datetime import datetime


class AdvertisementRepository:
    def __init__(self, db_path="advertisements.db"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._create_tables()

    def _create_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS advertisements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                caption TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'draft',
                category_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                published_at TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES categories(id)
            );

            CREATE TABLE IF NOT EXISTS advertisement_media (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                advertisement_id INTEGER NOT NULL,
                file_id TEXT NOT NULL,
                position INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (advertisement_id) REFERENCES advertisements(id) ON DELETE CASCADE
            );
        """)
        self.conn.commit()

    def create_draft(self, user_id, caption=""):
        cursor = self.conn.execute(
            "INSERT INTO advertisements (user_id, caption, status) VALUES (?, ?, 'draft')",
            (user_id, caption)
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_draft(self, user_id):
        row = self.conn.execute(
            "SELECT * FROM advertisements WHERE user_id = ? AND status = 'draft' ORDER BY id DESC LIMIT 1",
            (user_id,)
        ).fetchone()
        if row is None:
            return None
        ad = dict(row)
        media_rows = self.conn.execute(
            "SELECT file_id FROM advertisement_media WHERE advertisement_id = ? ORDER BY position",
            (ad["id"],)
        ).fetchall()
        ad["media"] = [r["file_id"] for r in media_rows]
        return ad

    def add_media(self, ad_id, file_id):
        pos = self.conn.execute(
            "SELECT COALESCE(MAX(position), -1) + 1 FROM advertisement_media WHERE advertisement_id = ?",
            (ad_id,)
        ).fetchone()[0]
        self.conn.execute(
            "INSERT INTO advertisement_media (advertisement_id, file_id, position) VALUES (?, ?, ?)",
            (ad_id, file_id, pos)
        )
        self.conn.commit()

    def append_text(self, ad_id, text):
        self.conn.execute(
            "UPDATE advertisements SET caption = caption || '\n' || ? WHERE id = ?",
            (text, ad_id)
        )
        self.conn.commit()

    def publish(self, ad_id):
        self.conn.execute(
            "UPDATE advertisements SET status = 'published', published_at = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), ad_id)
        )
        self.conn.commit()

    def discard(self, ad_id):
        self.conn.execute(
            "UPDATE advertisements SET status = 'discarded' WHERE id = ?",
            (ad_id,)
        )
        self.conn.commit()

    def remove_draft(self, user_id):
        self.conn.execute(
            "UPDATE advertisements SET status = 'discarded' WHERE user_id = ? AND status = 'draft'",
            (user_id,)
        )
        self.conn.commit()

    def get_ad_by_id(self, ad_id):
        row = self.conn.execute(
            "SELECT * FROM advertisements WHERE id = ?",
            (ad_id,)
        ).fetchone()
        if row is None:
            return None
        ad = dict(row)
        media_rows = self.conn.execute(
            "SELECT file_id FROM advertisement_media WHERE advertisement_id = ? ORDER BY position",
            (ad["id"],)
        ).fetchall()
        ad["media"] = [r["file_id"] for r in media_rows]
        return ad

    def repost(self, ad_id, user_id):
        original = self.get_ad_by_id(ad_id)
        if original is None:
            return None
        self.remove_draft(user_id)
        new_id = self.create_draft(user_id, original["caption"])
        for file_id in original["media"]:
            self.add_media(new_id, file_id)
        return new_id
