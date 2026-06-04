"""
Gestione utenti e ruoli per uso aziendale.
Ruoli: admin, operator, viewer
"""
from __future__ import annotations
import hashlib
import json
import os
import uuid
from dataclasses import dataclass, field
from typing import List, Optional

USERS_PATH = os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")),
    "PyMRemoteNG", "users.json"
)

ROLES = {
    "admin":    {"label": "Amministratore", "color": "#EF5350"},
    "operator": {"label": "Operatore",      "color": "#FFC107"},
    "viewer":   {"label": "Visualizzatore", "color": "#4EC94E"},
}

_PERMISSIONS = {
    "admin":    {"connect", "edit_connections", "manage_users",
                 "view_logs", "export_reports", "run_scripts", "manage_scheduler"},
    "operator": {"connect", "edit_connections", "view_logs",
                 "export_reports", "run_scripts"},
    "viewer":   {"connect", "view_logs"},
}


@dataclass
class AppUser:
    id:            str
    username:      str
    display_name:  str
    role:          str        # admin | operator | viewer
    password_hash: str        # SHA-256 hex
    active:        bool = True
    last_login:    str  = ""
    groups:        List[str] = field(default_factory=list)

    def check_password(self, pw: str) -> bool:
        return self.password_hash == hashlib.sha256(pw.encode()).hexdigest()

    def can(self, action: str) -> bool:
        return action in _PERMISSIONS.get(self.role, set())

    def role_label(self) -> str:
        return ROLES.get(self.role, {}).get("label", self.role)

    def role_color(self) -> str:
        return ROLES.get(self.role, {}).get("color", "#888888")

    def to_dict(self) -> dict:
        return {
            "id": self.id, "username": self.username,
            "display_name": self.display_name, "role": self.role,
            "password_hash": self.password_hash, "active": self.active,
            "last_login": self.last_login, "groups": self.groups,
        }

    @staticmethod
    def from_dict(d: dict) -> "AppUser":
        return AppUser(
            id=d.get("id", str(uuid.uuid4())),
            username=d.get("username", ""),
            display_name=d.get("display_name", ""),
            role=d.get("role", "viewer"),
            password_hash=d.get("password_hash", ""),
            active=d.get("active", True),
            last_login=d.get("last_login", ""),
            groups=d.get("groups", []),
        )


class UserManager:
    _instance: Optional["UserManager"] = None
    _current: Optional[AppUser] = None

    def __init__(self):
        self._users: List[AppUser] = []
        self.load()
        if not self._users:
            self._create_default_admin()

    @classmethod
    def get_instance(cls) -> "UserManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _create_default_admin(self):
        admin = AppUser(
            id=str(uuid.uuid4()),
            username="admin",
            display_name="Amministratore",
            role="admin",
            password_hash=hashlib.sha256("admin".encode()).hexdigest(),
        )
        self._users.append(admin)
        self.save()

    def load(self):
        if not os.path.exists(USERS_PATH):
            return
        try:
            with open(USERS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._users = [AppUser.from_dict(d) for d in data.get("users", [])]
        except Exception:
            pass

    def save(self):
        os.makedirs(os.path.dirname(USERS_PATH), exist_ok=True)
        with open(USERS_PATH, "w", encoding="utf-8") as f:
            json.dump({"users": [u.to_dict() for u in self._users]}, f, indent=2)

    def all(self) -> List[AppUser]:
        return list(self._users)

    def get(self, user_id: str) -> Optional[AppUser]:
        return next((u for u in self._users if u.id == user_id), None)

    def get_by_username(self, username: str) -> Optional[AppUser]:
        return next((u for u in self._users if u.username == username), None)

    def add(self, username: str, display_name: str,
            role: str, password: str) -> AppUser:
        u = AppUser(
            id=str(uuid.uuid4()),
            username=username,
            display_name=display_name or username,
            role=role,
            password_hash=hashlib.sha256(password.encode()).hexdigest(),
        )
        self._users.append(u)
        self.save()
        return u

    def update(self, user_id: str, display_name: str, role: str,
               password: str = "", active: bool = True):
        u = self.get(user_id)
        if u:
            u.display_name = display_name
            u.role = role
            u.active = active
            if password:
                u.password_hash = hashlib.sha256(password.encode()).hexdigest()
            self.save()

    def delete(self, user_id: str):
        self._users = [u for u in self._users if u.id != user_id]
        self.save()

    def authenticate(self, username: str, password: str) -> Optional[AppUser]:
        u = self.get_by_username(username)
        if u and u.active and u.check_password(password):
            from datetime import datetime
            u.last_login = datetime.now().isoformat(timespec="seconds")
            self.save()
            UserManager._current = u
            return u
        return None

    def current_user(self) -> Optional[AppUser]:
        return UserManager._current

    def set_current(self, user: Optional[AppUser]):
        UserManager._current = user
