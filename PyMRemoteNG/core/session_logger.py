"""
Session logger: registra connessioni, comandi SSH, eventi di audit.
Salva in shared/logs/ (condiviso team) con fallback su APPDATA locale.

Rotazione automatica: file più vecchi di MAX_LOG_DAYS vengono eliminati all'avvio.
Cache in-memory: get_all() non rilegge da disco se i dati hanno meno di CACHE_TTL secondi.
"""
from __future__ import annotations
import json
import os
import threading
import time
from datetime import datetime, timedelta
from typing import List, Optional

MAX_LOG_DAYS = 90    # file più vecchi vengono eliminati automaticamente
CACHE_TTL    = 30    # secondi prima di rileggere dal disco

_SHARED_LOG_DIR = os.path.normpath(os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "..", "shared", "logs"
))


def _get_log_dir() -> str:
    parent = os.path.dirname(_SHARED_LOG_DIR)
    if os.path.isdir(parent):
        d = _SHARED_LOG_DIR
    else:
        d = os.path.join(
            os.environ.get("APPDATA", os.path.expanduser("~")),
            "PyMRemoteNG", "logs"
        )
    os.makedirs(d, exist_ok=True)
    return d


class SessionEvent:
    def __init__(self, event_type: str, user: str, host: str,
                 protocol: str, detail: str = ""):
        self.ts       = datetime.now().isoformat(timespec="seconds")
        self.type     = event_type   # CONNECT | DISCONNECT | COMMAND | ERROR | AUTH
        self.user     = user
        self.host     = host
        self.protocol = protocol
        self.detail   = detail

    def to_dict(self) -> dict:
        return {
            "ts": self.ts, "type": self.type, "user": self.user,
            "host": self.host, "protocol": self.protocol, "detail": self.detail,
        }

    @staticmethod
    def from_dict(d: dict) -> "SessionEvent":
        ev = SessionEvent(
            d.get("type", ""), d.get("user", ""),
            d.get("host", ""), d.get("protocol", ""), d.get("detail", "")
        )
        ev.ts = d.get("ts", ev.ts)
        return ev


class SessionLogger:
    _instance: Optional["SessionLogger"] = None
    _lock = threading.Lock()

    def __init__(self):
        self._today_events: List[SessionEvent] = []
        self._cache: List[SessionEvent] = []
        self._cache_ts: float = 0.0          # epoch del'ultimo caricamento
        self._cache_days: int = 0
        self._load_today()
        self._purge_old_logs()

    def _purge_old_logs(self):
        """Elimina file di log più vecchi di MAX_LOG_DAYS."""
        log_dir = _get_log_dir()
        cutoff = datetime.now() - timedelta(days=MAX_LOG_DAYS)
        try:
            for fname in os.listdir(log_dir):
                if not (fname.startswith("session_") and fname.endswith(".json")):
                    continue
                try:
                    file_date = datetime.strptime(fname[8:18], "%Y-%m-%d")
                    if file_date < cutoff:
                        os.remove(os.path.join(log_dir, fname))
                except Exception:
                    pass
        except Exception:
            pass

    @classmethod
    def get_instance(cls) -> "SessionLogger":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _log_path(self, date: Optional[datetime] = None) -> str:
        d = date or datetime.now()
        return os.path.join(_get_log_dir(), f"session_{d.strftime('%Y-%m-%d')}.json")

    def _load_today(self):
        path = self._log_path()
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._today_events = [SessionEvent.from_dict(d) for d in data.get("events", [])]
        except Exception:
            pass

    def _save_today(self):
        path = self._log_path()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(
                    {"events": [e.to_dict() for e in self._today_events]},
                    f, indent=2, ensure_ascii=False
                )
        except Exception:
            pass

    def log(self, event_type: str, host: str, protocol: str,
            detail: str = "", user: str = ""):
        if not user:
            try:
                from core.user_manager import UserManager
                u = UserManager.get_instance().current_user()
                user = u.username if u else "system"
            except Exception:
                user = "system"
        ev = SessionEvent(event_type, user, host, protocol, detail)
        with self._lock:
            self._today_events.append(ev)
            self._save_today()
            self._cache_ts = 0.0   # invalida cache — il nuovo evento deve essere visibile

    def get_all(self, days: int = 30) -> List[SessionEvent]:
        """
        Ritorna tutti gli eventi degli ultimi `days` giorni.
        Usa la cache in-memory per CACHE_TTL secondi; evita di rileggere
        i file dal disco ad ogni chiamata (es. dashboard ogni 8s).
        """
        now = time.monotonic()
        with self._lock:
            if (self._cache
                    and self._cache_days == days
                    and now - self._cache_ts < CACHE_TTL):
                return list(self._cache)

        all_events: List[SessionEvent] = []
        log_dir = _get_log_dir()
        cutoff  = datetime.now() - timedelta(days=days)
        try:
            for fname in sorted(os.listdir(log_dir), reverse=True):
                if not (fname.startswith("session_") and fname.endswith(".json")):
                    continue
                try:
                    file_date = datetime.strptime(fname[8:18], "%Y-%m-%d")
                    if file_date < cutoff:
                        continue
                except Exception:
                    continue
                try:
                    with open(os.path.join(log_dir, fname), "r", encoding="utf-8") as f:
                        data = json.load(f)
                    all_events.extend(
                        SessionEvent.from_dict(d) for d in data.get("events", [])
                    )
                except Exception:
                    pass
        except Exception:
            pass

        result = sorted(all_events, key=lambda e: e.ts, reverse=True)
        with self._lock:
            self._cache      = result
            self._cache_ts   = time.monotonic()
            self._cache_days = days
        return result

    def invalidate_cache(self):
        """Invalida la cache (usata dopo log() o purge manuale)."""
        with self._lock:
            self._cache_ts = 0.0

    def purge_before(self, days_to_keep: int = 30) -> int:
        """
        Elimina i file di log più vecchi di `days_to_keep` giorni.
        Ritorna il numero di file eliminati.
        Usato dal log viewer per il pulsante 'Svuota log vecchi'.
        """
        log_dir = _get_log_dir()
        cutoff  = datetime.now() - timedelta(days=days_to_keep)
        removed = 0
        try:
            for fname in os.listdir(log_dir):
                if not (fname.startswith("session_") and fname.endswith(".json")):
                    continue
                try:
                    file_date = datetime.strptime(fname[8:18], "%Y-%m-%d")
                    if file_date < cutoff:
                        os.remove(os.path.join(log_dir, fname))
                        removed += 1
                except Exception:
                    pass
        except Exception:
            pass
        self.invalidate_cache()
        return removed
