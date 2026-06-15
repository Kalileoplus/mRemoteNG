"""
Gestione utenti e ruoli per uso aziendale.
Ruoli: admin, operator, viewer
"""
from __future__ import annotations
import hashlib
import hmac
import json
import logging
import os
import stat
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ── Funzioni di hashing sicuro ────────────────────────────────────────────────

def _hash_password(password: str) -> str:
    """PBKDF2-SHA256 con salt casuale. Formato: pbkdf2$iter$salt_hex$hash_hex"""
    salt = os.urandom(16)
    dk   = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100_000)
    return f"pbkdf2$100000${salt.hex()}${dk.hex()}"


def _check_password_hash(stored: str, password: str) -> bool:
    """
    Verifica la password. Supporta sia il nuovo formato PBKDF2
    sia il vecchio SHA-256 senza salt (legacy, upgrade automatico).
    """
    if stored.startswith('pbkdf2$'):
        try:
            _, iterations, salt_hex, hash_hex = stored.split('$')
            salt = bytes.fromhex(salt_hex)
            dk   = hashlib.pbkdf2_hmac('sha256', password.encode(),
                                       salt, int(iterations))
            return hmac.compare_digest(dk.hex(), hash_hex)
        except Exception:
            return False
    # Legacy: SHA-256 senza salt (backward compat — hash viene aggiornato al login)
    candidate = hashlib.sha256(password.encode()).hexdigest()
    return hmac.compare_digest(stored, candidate)

USERS_PATH = os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")),
    "Nexus", "users.json"
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

# Hash della password di default "admin" — usato per rilevare account non protetti
_DEFAULT_ADMIN_HASH = hashlib.sha256("admin".encode()).hexdigest()

# Password deboli/comuni non accettate
_WEAK_PASSWORDS = frozenset({
    "admin", "password", "password1", "123456", "12345678", "1234567890",
    "qwerty", "letmein", "welcome", "monkey", "dragon", "master",
    "hello", "login", "pass", "test", "user", "guest", "root",
    "abc123", "111111", "000000", "iloveyou", "sunshine", "princess",
})


@dataclass
class AppUser:
    id:                   str
    username:             str
    display_name:         str
    role:                 str        # admin | operator | viewer
    password_hash:        str        # SHA-256 hex
    active:               bool = True
    last_login:           str  = ""
    groups:               List[str] = field(default_factory=list)
    must_change_password: bool = False   # True = forza cambio al prossimo login

    def check_password(self, pw: str) -> bool:
        return _check_password_hash(self.password_hash, pw)

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
            "must_change_password": self.must_change_password,
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
            must_change_password=d.get("must_change_password", False),
        )


_MAX_ATTEMPTS  = 5      # tentativi prima del lockout
_LOCKOUT_SEC   = 30     # secondi di blocco dopo _MAX_ATTEMPTS fallimenti
_ATTEMPT_DELAY = 0.5    # delay minimo tra tentativi (frena brute force)


class UserManager:
    _instance: Optional["UserManager"] = None
    _current:  Optional[AppUser] = None
    # Tracking server-side: {username: (count, first_fail_ts)}
    _auth_track: Dict[str, tuple] = {}

    def __init__(self):
        self._users: List[AppUser] = []
        self.load()
        if not self._users:
            self._create_default_admin()
        else:
            self._flag_insecure_passwords()

    @classmethod
    def get_instance(cls) -> "UserManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _create_default_admin(self):
        """Crea l'utente admin di default con flag must_change_password=True."""
        admin = AppUser(
            id=str(uuid.uuid4()),
            username="admin",
            display_name="Amministratore",
            role="admin",
            password_hash=_DEFAULT_ADMIN_HASH,
            must_change_password=True,
        )
        self._users.append(admin)
        self.save()

    def _flag_insecure_passwords(self):
        """Imposta must_change_password=True per utenti con password di default."""
        changed = False
        for u in self._users:
            if u.password_hash == _DEFAULT_ADMIN_HASH and not u.must_change_password:
                u.must_change_password = True
                changed = True
        if changed:
            self.save()

    def load(self):
        if not os.path.exists(USERS_PATH):
            return
        # Verifica permessi file: su sistemi POSIX deve essere 0o600
        try:
            if os.name == 'posix':
                mode = stat.S_IMODE(os.stat(USERS_PATH).st_mode)
                if mode & 0o077:          # bit group/other non devono essere impostati
                    os.chmod(USERS_PATH, 0o600)
        except Exception:
            pass
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
        try:
            os.chmod(USERS_PATH, 0o600)
        except Exception:
            pass

    def all(self) -> List[AppUser]:
        return list(self._users)

    def get(self, user_id: str) -> Optional[AppUser]:
        return next((u for u in self._users if u.id == user_id), None)

    def get_by_username(self, username: str) -> Optional[AppUser]:
        return next((u for u in self._users if u.username == username), None)

    def add(self, username: str, display_name: str,
            role: str, password: str,
            must_change_password: bool = False) -> AppUser:
        u = AppUser(
            id=str(uuid.uuid4()),
            username=username,
            display_name=display_name or username,
            role=role,
            password_hash=_hash_password(password),
            must_change_password=must_change_password,
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
                u.password_hash = _hash_password(password)
                u.must_change_password = False
            self.save()

    def change_password(self, user_id: str, new_password: str) -> bool:
        """Cambia password e rimuove il flag must_change_password."""
        u = self.get(user_id)
        if not u:
            return False
        if new_password.lower().strip() in _WEAK_PASSWORDS:
            return False
        if len(new_password) < 8:
            return False
        u.password_hash = _hash_password(new_password)
        u.must_change_password = False
        self.save()
        return True

    def delete(self, user_id: str):
        self._users = [u for u in self._users if u.id != user_id]
        self.save()

    def authenticate(self, username: str, password: str) -> Optional[AppUser]:
        """
        Autentica un utente con rate limiting server-side.
        V6-03: il lockout vale anche se si bypassa la UI.
        """
        now = time.monotonic()

        # Controlla lockout per questo username
        count, first_ts = UserManager._auth_track.get(username, (0, now))
        elapsed = now - first_ts
        if count >= _MAX_ATTEMPTS and elapsed < _LOCKOUT_SEC:
            remaining = int(_LOCKOUT_SEC - elapsed)
            logging.warning(f"Login bloccato per '{username}': troppi tentativi. Attendere {remaining}s.")
            time.sleep(_ATTEMPT_DELAY)
            return None
        if elapsed >= _LOCKOUT_SEC:
            UserManager._auth_track.pop(username, None)
            count = 0

        # Delay minimo anti-brute-force
        time.sleep(_ATTEMPT_DELAY)

        u = self.get_by_username(username)
        if u and u.active and u.check_password(password):
            UserManager._auth_track.pop(username, None)  # reset fallimenti
            if not u.password_hash.startswith('pbkdf2$'):
                u.password_hash = _hash_password(password)
            from datetime import datetime
            u.last_login = datetime.now().isoformat(timespec="seconds")
            self.save()
            logging.info(f"Login riuscito: '{username}' (ruolo: {u.role})")
            UserManager._current = u
            return u

        # Fallimento: aggiorna tracking
        new_count = count + 1
        UserManager._auth_track[username] = (new_count, first_ts if count > 0 else now)
        logging.warning(f"Login fallito per '{username}' (tentativo {new_count}/{_MAX_ATTEMPTS}).")
        return None

    def current_user(self) -> Optional[AppUser]:
        return UserManager._current

    def set_current(self, user: Optional[AppUser]):
        """
        Imposta l'utente corrente.
        V6-04: logga ogni cambio di sessione per audit trail.
        """
        prev = UserManager._current
        prev_name = prev.username if prev else "None"
        new_name  = user.username if user else "None"
        if prev_name != new_name:
            logging.info(f"Sessione cambiata: '{prev_name}' → '{new_name}'")
        UserManager._current = user
