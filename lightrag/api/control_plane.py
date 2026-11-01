"""Small SQLite control plane for local users and workspaces."""

from __future__ import annotations

import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .passwords import hash_password


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ControlPlane:
    """Persist users, workspaces, and workspace memberships in SQLite."""

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=10000")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _initialize_schema(self) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('admin', 'user')),
                    status TEXT NOT NULL CHECK (status IN ('active', 'disabled')),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_login_at TEXT
                );
                CREATE TABLE IF NOT EXISTS workspaces (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    slug TEXT NOT NULL UNIQUE,
                    description TEXT NOT NULL DEFAULT '',
                    storage_namespace TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('active', 'archived')),
                    owner_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (owner_id) REFERENCES users(id)
                );
                CREATE TABLE IF NOT EXISTS workspace_members (
                    workspace_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('admin', 'editor', 'viewer')),
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (workspace_id, user_id),
                    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                """
            )

    def initialize_defaults(
        self,
        *,
        username: str,
        password: str | None,
        workspace_name: str,
        workspace_slug: str,
        storage_namespace: str,
    ) -> dict[str, str] | None:
        """Create the first administrator and configured default workspace."""
        with self._lock, self._connect() as connection:
            user = connection.execute(
                "SELECT id FROM users WHERE username = ?", (username,)
            ).fetchone()
            if user is None and password:
                user_id = f"user_{uuid.uuid4().hex[:12]}"
                now = _now()
                connection.execute(
                    """INSERT INTO users
                    (id, username, password_hash, display_name, role, status,
                     created_at, updated_at)
                    VALUES (?, ?, ?, ?, 'admin', 'active', ?, ?)""",
                    (user_id, username, hash_password(password), username, now, now),
                )
            user = connection.execute(
                "SELECT id FROM users WHERE username = ?", (username,)
            ).fetchone()
            if user is None:
                return None
            workspace = connection.execute(
                "SELECT id FROM workspaces WHERE slug = ?", (workspace_slug,)
            ).fetchone()
            if workspace is None:
                workspace_id = f"workspace_{uuid.uuid4().hex[:12]}"
                now = _now()
                connection.execute(
                    """INSERT INTO workspaces
                    (id, name, slug, description, storage_namespace, status,
                     owner_id, created_at, updated_at)
                    VALUES (?, ?, ?, '', ?, 'active', ?, ?, ?)""",
                    (workspace_id, workspace_name, workspace_slug,
                     storage_namespace, user["id"], now, now),
                )
            workspace = connection.execute(
                "SELECT id FROM workspaces WHERE slug = ?", (workspace_slug,)
            ).fetchone()
            connection.execute(
                """INSERT INTO workspace_members
                (workspace_id, user_id, role, created_at)
                VALUES (?, ?, 'admin', ?)
                ON CONFLICT(workspace_id, user_id) DO UPDATE SET role='admin'""",
                (workspace["id"], user["id"], _now()),
            )
            return {"user_id": user["id"], "workspace_id": workspace["id"]}

    def get_user(self, username: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
            return dict(row) if row else None

    def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            return dict(row) if row else None

    def list_users(self) -> list[dict[str, Any]]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """SELECT id, username, display_name, role, status,
                   created_at, updated_at, last_login_at FROM users
                   ORDER BY username"""
            ).fetchall()
            return [dict(row) for row in rows]

    def create_user(
        self, username: str, password: str, display_name: str, role: str
    ) -> dict[str, Any]:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        now = _now()
        with self._lock, self._connect() as connection:
            try:
                connection.execute(
                    """INSERT INTO users
                    (id, username, password_hash, display_name, role, status,
                     created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, 'active', ?, ?)""",
                    (user_id, username, hash_password(password), display_name,
                     role, now, now),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError("Username already exists") from exc
        return self.get_user(username) or {}

    def update_user(
        self, user_id: str, *, display_name: str | None = None,
        role: str | None = None, status: str | None = None,
        password: str | None = None,
    ) -> dict[str, Any] | None:
        fields: list[str] = []
        values: list[Any] = []
        if display_name is not None:
            fields.append("display_name = ?")
            values.append(display_name)
        if role is not None:
            fields.append("role = ?")
            values.append(role)
        if status is not None:
            fields.append("status = ?")
            values.append(status)
        if password is not None:
            fields.append("password_hash = ?")
            values.append(hash_password(password))
        if fields:
            fields.append("updated_at = ?")
            values.extend([_now(), user_id])
            with self._lock, self._connect() as connection:
                connection.execute(
                    f"UPDATE users SET {', '.join(fields)} WHERE id = ?", values
                )
        return self.get_user_by_id(user_id)

    def record_login(self, user_id: str) -> None:
        with self._lock, self._connect() as connection:
            now = _now()
            connection.execute(
                "UPDATE users SET last_login_at = ?, updated_at = ? WHERE id = ?",
                (now, now, user_id),
            )

    def list_workspaces(self, user_id: str | None = None) -> list[dict[str, Any]]:
        with self._lock, self._connect() as connection:
            if user_id:
                rows = connection.execute(
                    """SELECT w.*, m.role AS member_role FROM workspaces w
                    JOIN workspace_members m ON m.workspace_id = w.id
                    WHERE m.user_id = ? AND w.status = 'active'
                    ORDER BY w.name""", (user_id,)
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM workspaces ORDER BY name"
                ).fetchall()
            return [dict(row) for row in rows]

    def create_workspace(
        self, *, name: str, slug: str, description: str,
        storage_namespace: str, owner_id: str,
    ) -> dict[str, Any]:
        workspace_id = f"workspace_{uuid.uuid4().hex[:12]}"
        now = _now()
        with self._lock, self._connect() as connection:
            try:
                connection.execute(
                    """INSERT INTO workspaces
                    (id, name, slug, description, storage_namespace, status,
                     owner_id, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?)""",
                    (workspace_id, name, slug, description, storage_namespace,
                     owner_id, now, now),
                )
                connection.execute(
                    """INSERT INTO workspace_members
                    (workspace_id, user_id, role, created_at)
                    VALUES (?, ?, 'admin', ?)""", (workspace_id, owner_id, now)
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError("Workspace slug already exists") from exc
        return self.get_workspace(workspace_id) or {}

    def get_workspace(self, workspace_id: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM workspaces WHERE id = ?", (workspace_id,)
            ).fetchone()
            return dict(row) if row else None

    def update_workspace(
        self, workspace_id: str, *, name: str | None, description: str | None
    ) -> dict[str, Any] | None:
        fields: list[str] = []
        values: list[Any] = []
        if name is not None:
            fields.append("name = ?")
            values.append(name)
        if description is not None:
            fields.append("description = ?")
            values.append(description)
        if fields:
            fields.append("updated_at = ?")
            values.extend([_now(), workspace_id])
            with self._lock, self._connect() as connection:
                connection.execute(
                    f"UPDATE workspaces SET {', '.join(fields)} WHERE id = ?",
                    values,
                )
        return self.get_workspace(workspace_id)

    def archive_workspace(self, workspace_id: str) -> bool:
        with self._lock, self._connect() as connection:
            result = connection.execute(
                "UPDATE workspaces SET status='archived', updated_at=? WHERE id=?",
                (_now(), workspace_id),
            )
            return result.rowcount > 0

    def get_members(self, workspace_id: str) -> list[dict[str, Any]]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """SELECT u.id, u.username, u.display_name, u.status,
                   m.role, m.created_at FROM workspace_members m
                   JOIN users u ON u.id = m.user_id
                   WHERE m.workspace_id = ? ORDER BY u.username""", (workspace_id,)
            ).fetchall()
            return [dict(row) for row in rows]

    def get_member_role(self, workspace_id: str, user_id: str) -> str | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """SELECT role FROM workspace_members
                   WHERE workspace_id = ? AND user_id = ?""",
                (workspace_id, user_id),
            ).fetchone()
            return row["role"] if row else None

    def set_member(self, workspace_id: str, user_id: str, role: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """INSERT INTO workspace_members
                (workspace_id, user_id, role, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(workspace_id, user_id)
                DO UPDATE SET role=excluded.role""",
                (workspace_id, user_id, role, _now()),
            )

    def remove_member(self, workspace_id: str, user_id: str) -> bool:
        with self._lock, self._connect() as connection:
            result = connection.execute(
                "DELETE FROM workspace_members WHERE workspace_id=? AND user_id=?",
                (workspace_id, user_id),
            )
            return result.rowcount > 0
