"""
Credential manager: salva/carica credenziali per RDP (e altri protocolli).
Le password sono criptate con lo stesso modulo crypto usato per le connessioni.
"""
from __future__ import annotations
import json
import os
import uuid
from dataclasses import dataclass, field
from typing import List, Optional

CREDS_PATH = os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")),
    "Nexus", "credentials.json"
)


@dataclass
class SavedCredential:
    id:       str
    name:     str        # etichetta leggibile, es. "Admin dominio ACME"
    username: str
    password_enc: str    # password criptata
    domain:   str = ""

    def get_password(self) -> str:
        from core.crypto import decrypt
        try:
            return decrypt(self.password_enc) if self.password_enc else ""
        except Exception:
            return ""

    def to_dict(self) -> dict:
        return {
            "id":           self.id,
            "name":         self.name,
            "username":     self.username,
            "password_enc": self.password_enc,
            "domain":       self.domain,
        }

    @staticmethod
    def from_dict(d: dict) -> "SavedCredential":
        if not isinstance(d, dict):
            raise ValueError("Formato credenziale non valido.")
        return SavedCredential(
            id=str(d.get("id", uuid.uuid4()))[:64],
            name=str(d.get("name", ""))[:256],
            username=str(d.get("username", ""))[:256],
            password_enc=str(d.get("password_enc", ""))[:8192],
            domain=str(d.get("domain", ""))[:256],
        )


class CredentialManager:
    """Singleton-like manager: usa get_instance()."""
    _instance: Optional["CredentialManager"] = None

    def __init__(self):
        self._creds: List[SavedCredential] = []
        self.load()

    @classmethod
    def get_instance(cls) -> "CredentialManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def load(self):
        if not os.path.exists(CREDS_PATH):
            return
        try:
            with open(CREDS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._creds = [SavedCredential.from_dict(d) for d in data.get("credentials", [])]
        except Exception:
            pass

    def save(self):
        os.makedirs(os.path.dirname(CREDS_PATH), exist_ok=True)
        with open(CREDS_PATH, "w", encoding="utf-8") as f:
            json.dump({"credentials": [c.to_dict() for c in self._creds]}, f, indent=2)

    def all(self) -> List[SavedCredential]:
        return list(self._creds)

    def add(self, name: str, username: str, password: str, domain: str = "") -> SavedCredential:
        from core.crypto import encrypt
        cred = SavedCredential(
            id=str(uuid.uuid4()),
            name=name or username,
            username=username,
            password_enc=encrypt(password),
            domain=domain,
        )
        self._creds.append(cred)
        self.save()
        return cred

    def update(self, cred_id: str, name: str, username: str,
               password: str, domain: str = ""):
        from core.crypto import encrypt
        for c in self._creds:
            if c.id == cred_id:
                c.name     = name or username
                c.username = username
                c.domain   = domain
                if password:
                    c.password_enc = encrypt(password)
                self.save()
                return

    def delete(self, cred_id: str):
        self._creds = [c for c in self._creds if c.id != cred_id]
        self.save()

    def get(self, cred_id: str) -> Optional[SavedCredential]:
        for c in self._creds:
            if c.id == cred_id:
                return c
        return None
