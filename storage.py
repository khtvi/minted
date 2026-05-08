import json
import os
import sqlite3
import time


class SQLiteUserStore:
    def __init__(self, db_path):
        self.db_path = self._resolve_db_path(db_path)
        self._fallback_db_path = self._project_fallback_path(self.db_path)
        self._ensure_schema()

    def _project_fallback_path(self, db_path):
        fallback_dir = os.path.dirname(os.path.abspath(__file__))
        fallback_name = os.path.basename(db_path) or "storage.db"
        return os.path.join(fallback_dir, fallback_name)

    def _is_open_db_error(self, error):
        message = str(error).lower()
        return (
            "unable to open database file" in message
            or "access is denied" in message
        )

    def _resolve_db_path(self, db_path):
        requested_path = os.path.abspath(db_path)
        directory = os.path.dirname(requested_path)
        if directory:
            try:
                os.makedirs(directory, exist_ok=True)
                return requested_path
            except OSError:
                # Fall back to the project directory when system paths are not writable.
                return self._project_fallback_path(requested_path)
        return requested_path

    def _connect(self):
        connection = None
        try:
            connection = sqlite3.connect(self.db_path, timeout=30)
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=NORMAL")
            connection.execute("PRAGMA busy_timeout=30000")
            return connection
        except sqlite3.OperationalError as exc:
            if connection is not None:
                connection.close()
            if self._is_open_db_error(exc) and self.db_path != self._fallback_db_path:
                self.db_path = self._fallback_db_path
                fallback_connection = sqlite3.connect(self.db_path, timeout=30)
                fallback_connection.execute("PRAGMA journal_mode=WAL")
                fallback_connection.execute("PRAGMA synchronous=NORMAL")
                fallback_connection.execute("PRAGMA busy_timeout=30000")
                return fallback_connection
            raise

    def _run_with_retry(self, operation):
        last_error = None
        for attempt in range(4):
            try:
                return operation()
            except sqlite3.OperationalError as exc:
                message = str(exc).lower()
                if "locked" not in message and "busy" not in message:
                    raise
                last_error = exc
                time.sleep(0.08 * (attempt + 1))
        raise RuntimeError("SQLite database is busy. Please retry.") from last_error

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
        def _read():
            with self._connect() as connection:
                cursor = connection.execute("SELECT users_json FROM app_state WHERE id = 1")
                return cursor.fetchone()

        row = self._run_with_retry(_read)
        if not row or not row[0]:
            return []
        data = json.loads(row[0])
        return data if isinstance(data, list) else []

    def write_users(self, users):
        if not isinstance(users, list):
            raise ValueError("users must be a list")
        payload = json.dumps(users)

        def _write():
            with self._connect() as connection:
                connection.execute(
                    "UPDATE app_state SET users_json = ? WHERE id = 1",
                    (payload,),
                )
                connection.commit()

        self._run_with_retry(_write)

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
