from __future__ import annotations

from typing import Any, Optional

import aiosqlite

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id    INTEGER PRIMARY KEY,
    full_name  TEXT,
    username   TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS movies (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    code       TEXT NOT NULL UNIQUE COLLATE NOCASE,
    title      TEXT NOT NULL DEFAULT '',
    language   TEXT NOT NULL DEFAULT '',
    quality    TEXT NOT NULL DEFAULT '',
    genre      TEXT NOT NULL DEFAULT '',
    category   TEXT NOT NULL DEFAULT '',
    caption    TEXT NOT NULL DEFAULT '',
    poster_id  TEXT NOT NULL DEFAULT '',
    file_id    TEXT NOT NULL,
    file_type  TEXT NOT NULL DEFAULT 'video',
    views      INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS channels (
    chat_id     INTEGER PRIMARY KEY,
    title       TEXT NOT NULL DEFAULT '',
    username    TEXT,
    invite_link TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


class Database:
    def __init__(self, path: str = DB_PATH) -> None:
        self.path = path
        self._conn: Optional[aiosqlite.Connection] = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Baza ulanmagan. Avval db.connect() chaqiring.")
        return self._conn

    async def connect(self) -> None:
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(SCHEMA)
        await self._migrate()
        await self._conn.commit()

    async def _migrate(self) -> None:
        """Eski bazaga yangi ustunlarni qo'shadi (ma'lumotlar saqlanib qoladi)."""
        async with self.conn.execute("PRAGMA table_info(movies)") as cur:
            existing = {row["name"] for row in await cur.fetchall()}
        for column in ("language", "quality", "genre", "category", "poster_id"):
            if column not in existing:
                await self.conn.execute(
                    f"ALTER TABLE movies ADD COLUMN {column} TEXT NOT NULL DEFAULT ''"
                )

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    # ---------- ichki yordamchilar ----------

    async def _fetchone(self, sql: str, params: tuple = ()) -> Optional[aiosqlite.Row]:
        async with self.conn.execute(sql, params) as cur:
            return await cur.fetchone()

    async def _fetchall(self, sql: str, params: tuple = ()) -> list[aiosqlite.Row]:
        async with self.conn.execute(sql, params) as cur:
            return list(await cur.fetchall())

    async def _scalar(self, sql: str, params: tuple = ()) -> Any:
        row = await self._fetchone(sql, params)
        return row[0] if row else None

    # ---------- foydalanuvchilar ----------

    async def add_user(self, user_id: int, full_name: str, username: str | None) -> bool:
        """Yangi foydalanuvchi bo'lsa True qaytaradi."""
        async with self.conn.execute(
            "INSERT OR IGNORE INTO users (user_id, full_name, username) VALUES (?, ?, ?)",
            (user_id, full_name, username),
        ) as cur:
            created = cur.rowcount > 0
        if not created:
            await self.conn.execute(
                "UPDATE users SET full_name = ?, username = ? WHERE user_id = ?",
                (full_name, username, user_id),
            )
        await self.conn.commit()
        return created

    async def count_users(self) -> int:
        return await self._scalar("SELECT COUNT(*) FROM users") or 0

    async def count_users_since(self, days: int) -> int:
        return await self._scalar(
            "SELECT COUNT(*) FROM users WHERE created_at >= datetime('now', ?)",
            (f"-{days} days",),
        ) or 0

    async def all_user_ids(self) -> list[int]:
        rows = await self._fetchall("SELECT user_id FROM users")
        return [row["user_id"] for row in rows]

    # ---------- kinolar ----------

    async def add_movie(
        self,
        code: str,
        title: str,
        file_id: str,
        file_type: str = "video",
        language: str = "",
        quality: str = "",
        genre: str = "",
        category: str = "",
        caption: str = "",
        poster_id: str = "",
    ) -> bool:
        """Kod band bo'lsa False qaytaradi."""
        try:
            await self.conn.execute(
                """
                INSERT INTO movies
                    (code, title, language, quality, genre, category, caption,
                     poster_id, file_id, file_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (code, title, language, quality, genre, category, caption,
                 poster_id, file_id, file_type),
            )
        except aiosqlite.IntegrityError:
            return False
        await self.conn.commit()
        return True

    async def get_movie_by_code(self, code: str) -> Optional[aiosqlite.Row]:
        return await self._fetchone("SELECT * FROM movies WHERE code = ?", (code,))

    async def get_movie(self, movie_id: int) -> Optional[aiosqlite.Row]:
        return await self._fetchone("SELECT * FROM movies WHERE id = ?", (movie_id,))

    async def search_movies(self, query: str, limit: int = 15) -> list[aiosqlite.Row]:
        pattern = f"%{query}%"
        return await self._fetchall(
            """
            SELECT * FROM movies
            WHERE title LIKE ? OR caption LIKE ? OR genre LIKE ? OR language LIKE ?
            ORDER BY views DESC, id DESC
            LIMIT ?
            """,
            (pattern, pattern, pattern, pattern, limit),
        )

    async def list_movies(self, offset: int = 0, limit: int = 8) -> list[aiosqlite.Row]:
        return await self._fetchall(
            "SELECT * FROM movies ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset)
        )

    async def count_movies(self) -> int:
        return await self._scalar("SELECT COUNT(*) FROM movies") or 0

    async def total_views(self) -> int:
        return await self._scalar("SELECT COALESCE(SUM(views), 0) FROM movies") or 0

    async def top_movies(self, limit: int = 5) -> list[aiosqlite.Row]:
        return await self._fetchall(
            "SELECT * FROM movies ORDER BY views DESC, id DESC LIMIT ?", (limit,)
        )

    async def increment_views(self, movie_id: int) -> None:
        await self.conn.execute("UPDATE movies SET views = views + 1 WHERE id = ?", (movie_id,))
        await self.conn.commit()

    async def update_movie_field(self, movie_id: int, field: str, value: str) -> bool:
        if field not in {"code", "title", "language", "quality", "genre", "category", "caption"}:
            raise ValueError(f"Ruxsat etilmagan maydon: {field}")
        try:
            await self.conn.execute(
                f"UPDATE movies SET {field} = ? WHERE id = ?", (value, movie_id)
            )
        except aiosqlite.IntegrityError:
            return False
        await self.conn.commit()
        return True

    async def delete_movie(self, movie_id: int) -> None:
        await self.conn.execute("DELETE FROM movies WHERE id = ?", (movie_id,))
        await self.conn.commit()

    # ---------- sozlamalar ----------

    async def get_setting(self, key: str, default: str = "") -> str:
        value = await self._scalar("SELECT value FROM settings WHERE key = ?", (key,))
        return default if value is None else value

    async def set_setting(self, key: str, value: str) -> None:
        await self.conn.execute(
            """
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )
        await self.conn.commit()

    async def delete_setting(self, key: str) -> None:
        await self.conn.execute("DELETE FROM settings WHERE key = ?", (key,))
        await self.conn.commit()

    # ---------- majburiy obuna kanallari ----------

    async def add_channel(
        self, chat_id: int, title: str, username: str | None, invite_link: str | None
    ) -> None:
        await self.conn.execute(
            """
            INSERT INTO channels (chat_id, title, username, invite_link)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                title = excluded.title,
                username = excluded.username,
                invite_link = excluded.invite_link
            """,
            (chat_id, title, username, invite_link),
        )
        await self.conn.commit()

    async def list_channels(self) -> list[aiosqlite.Row]:
        return await self._fetchall("SELECT * FROM channels ORDER BY rowid")

    async def count_channels(self) -> int:
        return await self._scalar("SELECT COUNT(*) FROM channels") or 0

    async def delete_channel(self, chat_id: int) -> None:
        await self.conn.execute("DELETE FROM channels WHERE chat_id = ?", (chat_id,))
        await self.conn.commit()


db = Database()
