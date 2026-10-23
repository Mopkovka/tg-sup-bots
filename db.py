import sqlite3
from datetime import UTC, datetime

from config import DB_PATH


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                topic TEXT,
                text TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                created_at TEXT NOT NULL,
                support_msg_id INTEGER
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tickets_support_msg "
            "ON tickets (support_msg_id)"
        )
        # Каждое сообщение, отправленное в служебную группу, связано с тикетом
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS support_messages (
                support_msg_id INTEGER PRIMARY KEY,
                ticket_id INTEGER NOT NULL,
                FOREIGN KEY (ticket_id) REFERENCES tickets (id)
            )
            """
        )
        # Перенос связей, которые уже есть в старой базе
        conn.execute(
            "INSERT OR IGNORE INTO support_messages (support_msg_id, ticket_id) "
            "SELECT support_msg_id, id FROM tickets WHERE support_msg_id IS NOT NULL"
        )


def create_ticket(user_id: int, username: str | None, topic: str | None, text: str) -> int:
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            "INSERT INTO tickets (user_id, username, topic, text, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, username, topic, text, datetime.now(UTC).isoformat()),
        )
        return int(cur.lastrowid or 0)


def set_support_msg(ticket_id: int, msg_id: int) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE tickets SET support_msg_id = ? WHERE id = ?",
            (msg_id, ticket_id),
        )
        conn.execute(
            "INSERT OR REPLACE INTO support_messages (support_msg_id, ticket_id) "
            "VALUES (?, ?)",
            (msg_id, ticket_id),
        )


def get_ticket_by_support_msg(msg_id: int) -> tuple[int, int] | None:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT t.id, t.user_id FROM support_messages s "
            "JOIN tickets t ON t.id = s.ticket_id "
            "WHERE s.support_msg_id = ?",
            (msg_id,),
        ).fetchone()
    if row is None:
        return None
    return int(row[0]), int(row[1])


def get_open_ticket_for_user(user_id: int) -> int | None:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT id FROM tickets WHERE user_id = ? AND status = 'open' "
            "ORDER BY id DESC LIMIT 1",
            (user_id,),
        ).fetchone()
    return int(row[0]) if row else None


def get_ticket_status(ticket_id: int) -> str | None:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT status FROM tickets WHERE id = ?", (ticket_id,)
        ).fetchone()
    return str(row[0]) if row else None


def close_ticket(ticket_id: int) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE tickets SET status = 'closed' WHERE id = ?", (ticket_id,)
        )