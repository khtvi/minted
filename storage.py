import json
import os
import sqlite3


class SQLiteUserStore:
    def __init__(self, db_path):
        self.db_path = db_path
        directory = os.path.dirname(os.path.abspath(db_path))
        if directory:
            os.makedirs(directory, exist_ok=True)
        self._ensure_schema()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _ensure_schema(self):
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS app_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    users_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "INSERT OR IGNORE INTO app_state (id, users_json) VALUES (1, '[]')"
            )
            connection.commit()

    def read_users(self):
        with self._connect() as connection:
            cursor = connection.execute("SELECT users_json FROM app_state WHERE id = 1")
            row = cursor.fetchone()
        if not row or not row[0]:
            return []
        data = json.loads(row[0])
        return data if isinstance(data, list) else []

    def write_users(self, users):
        if not isinstance(users, list):
            raise ValueError("users must be a list")
        payload = json.dumps(users)
        with self._connect() as connection:
            connection.execute(
                "UPDATE app_state SET users_json = ? WHERE id = 1",
                (payload,),
            )
            connection.commit()

    def migrate_from_json(self, json_path):
        if not json_path or not os.path.exists(json_path):
            return

        try:
            with open(json_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return

        if not isinstance(data, list):
            return

        current_users = self.read_users()
        if current_users:
            return

        self.write_users(data)