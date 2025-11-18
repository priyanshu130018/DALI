"""Database manager implementation.

Supports SQLite by default and optional MySQL when environment variables are configured.
"""

import os
import json
import sqlite3
from typing import Optional, Dict, Any, List, Tuple

try:
    import mysql.connector  # type: ignore
except Exception:
    mysql = None  # type: ignore


class DBManager:
    def __init__(self) -> None:
        self.use_mysql = all(
            [
                os.environ.get("MYSQL_HOST"),
                os.environ.get("MYSQL_USER"),
                os.environ.get("MYSQL_PASSWORD"),
                os.environ.get("MYSQL_DB"),
            ]
        ) and (mysql is not None)

        if self.use_mysql:
            try:
                self.conn = mysql.connector.connect(
                    host=os.environ["MYSQL_HOST"],
                    user=os.environ["MYSQL_USER"],
                    password=os.environ["MYSQL_PASSWORD"],
                    database=os.environ["MYSQL_DB"],
                )
            except Exception:
                self.use_mysql = False
        if not self.use_mysql:
            db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "conversation.db")
            self.conn = sqlite3.connect(os.path.abspath(db_path), check_same_thread=False)

        self._ensure_schema()

    def _ensure_schema(self) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                mode TEXT,
                language TEXT,
                user_text TEXT,
                response_text TEXT,
                metadata TEXT
            )
            """
        )
        self.conn.commit()

    def insert_conversation(
        self,
        user_text: str,
        response_text: str,
        mode: str,
        language: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        meta_json = json.dumps(metadata or {})
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO conversations (mode, language, user_text, response_text, metadata)
            VALUES (?, ?, ?, ?, ?)
            """,
            (mode, language, user_text, response_text, meta_json),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def list_conversations(self, limit: int = 50) -> List[Tuple]:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT id, timestamp, mode, language, user_text, response_text, metadata FROM conversations ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return cur.fetchall()

    def get_conversation(self, conv_id: int) -> Optional[Tuple]:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT id, timestamp, mode, language, user_text, response_text, metadata FROM conversations WHERE id = ?",
            (conv_id,),
        )
        return cur.fetchone()

    def delete_conversation(self, conv_id: int) -> None:
        cur = self.conn.cursor()
        cur.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
        self.conn.commit()

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass