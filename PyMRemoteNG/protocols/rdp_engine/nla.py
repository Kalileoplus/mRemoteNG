"""
NLA (Network Level Authentication) via CredSSP + NTLM.
Usa win32security SSPI nativo di Windows.
Basato su MS-CSSP spec.
"""
import struct
import os
from typing import Optional


# ── ASN.1 DER helpers ────────────────────────────────────────────────────────

def _asn_len(n: int) -> bytes:
    if n < 0x80:
        return bytes([n])
    elif n < 0x100:
        return bytes([0x81, n])
    else:
        return bytes([0x82, (n >> 8) & 0xFF, n & 0xFF])


def _asn_tag(tag: int, data: bytes) -> bytes:
    return bytes([tag]) + _asn_len(len(data)) + data


def _asn_seq(data: bytes) -> bytes:
    return _asn_tag(0x30, data)


def _asn_octet(data: bytes) -> bytes:
    return _asn_tag(0x04, data)


def _asn_int(n: int) -> bytes:
    return _asn_tag(0x02, bytes([n]))


def _asn_ctx(ctx: int, constructed: bool, data: bytes) -> bytes:
    tag = (0xA0 if constructed else 0x80) | ctx
    return bytes([tag]) + _asn_len(len(data)) + data


def _asn_parse_len(data: bytes, offset: int):
    b = data[offset]
    if b < 0x80:
        return b, offset + 1
    nb = b & 0x7F
    val = int.from_bytes(data[offset + 1: offset + 1 + nb], "big")
    return val, offset + 1 + nb


def _asn_parse(data: bytes, offset: int):
    """Parsa tag, length, value. Ritorna (tag, value_bytes, next_offset)."""
    if offset >= len(data):
        raise ValueError("Offset fuori dal range")
    tag = data[offset]
    length, offset = _asn_parse_len(data, offset + 1)
    return tag, data[offset: offset + length], offset + length


# ── TSRequest encoding (MS-CSSP §2.2.1) ──────────────────────────────────────

def ts_request_encode(version: int = 6,
                      nego_token: Optional[bytes] = None,
                      auth_info: Optional[bytes] = None,
                      pub_key_auth: Optional[bytes] = None,
                      client_nonce: Optional[bytes] = None) -> bytes:
    """
    Codifica un TSRequest DER.
    Struttura corretta per negoTokens:
      [1] { SEQUENCE_OF { SEQUENCE { [0] { OCTET STRING } } } }
    """
    fields = _asn_ctx(0, True, _asn_int(version))

    if nego_token is not None:
        # NegoData ::= SEQUENCE OF NegoDataItem
        # NegoDataItem ::= SEQUENCE { negoToken [0] EXPLICIT OCTET STRING }
        nego_item = _asn_seq(_asn_ctx(0, True, _asn_octet(nego_token)))
        nego_data = _asn_seq(nego_item)   # SEQUENCE OF con un item
        fields += _asn_ctx(1, True, nego_data)

    if auth_info is not None:
        fields += _asn_ctx(2, True, _asn_octet(auth_info))

    if pub_key_auth is not None:
        fields += _asn_ctx(3, True, _asn_octet(pub_key_auth))

    if client_nonce is not None:
        fields += _asn_ctx(5, True, _asn_octet(client_nonce))

    return _asn_seq(fields)


def ts_request_decode(data: bytes) -> dict:
    """Decodifica TSRequest dal server."""
    result = {}
    try:
        tag, inner, _ = _asn_parse(data, 0)
        if tag != 0x30:
            return result
        offset = 0
        while offset < len(inner):
            tag, value, offset = _asn_parse(inner, offset)
            ctx = tag & 0x1F
            if ctx == 0:    # version
                result["version"] = value[-1] if value else 6
            elif ctx == 1:  # negoTokens: [1] { SEQUENCE { SEQUENCE { [0] { OCTET STRING } } } }
                try:
                    # SEQUENCE OF
                    _, seq_of, _ = _asn_parse(value, 0)
                    # NegoDataItem SEQUENCE
                    _, item_seq, _ = _asn_parse(seq_of, 0)
                    # [0] context
                    _, ctx_val, _ = _asn_parse(item_seq, 0)
                    # OCTET STRING
                    _, tok, _ = _asn_parse(ctx_val, 0)
                    result["negoToken"] = tok
                except Exception:
                    pass
            elif ctx == 3:  # pubKeyAuth
                try:
                    _, pk, _ = _asn_parse(value, 0)
                    result["pubKeyAuth"] = pk
                except Exception:
                    pass
    except Exception:
        pass
    return result


def ts_credentials_encode(username: str, password: str, domain: str = "") -> bytes:
    """Crea TSCredentials per l'invio finale."""
    uname = username.encode("utf-16-le")
    pwd   = password.encode("utf-16-le")
    dom   = domain.encode("utf-16-le")
    ts_password = _asn_seq(
        _asn_ctx(0, True, _asn_octet(dom)) +
        _asn_ctx(1, True, _asn_octet(uname)) +
        _asn_ctx(2, True, _asn_octet(pwd))
    )
    return _asn_seq(
        _asn_ctx(0, True, _asn_int(1)) +
        _asn_ctx(1, True, _asn_octet(ts_password))
    )


# ── SSPI NTLM Auth ────────────────────────────────────────────────────────────

class SSPIAuth:
    """NTLM authentication via Windows SSPI (pywin32)."""

    def __init__(self, username: str, password: str, domain: str, targetspn: str = ""):
        import sspi
        auth_info = (domain, username, password)
        self._auth = sspi.ClientAuth(
            "NTLM",
            targetspn=targetspn,
            auth_info=auth_info,
        )

    def get_negotiate(self) -> bytes:
        err, out_buf = self._auth.authorize(None)
        return out_buf[0].Buffer if out_buf else b""

    def get_authenticate(self, challenge: bytes) -> bytes:
        err, out_buf = self._auth.authorize(challenge)
        return out_buf[0].Buffer if out_buf else b""

    def encrypt(self, data: bytes) -> bytes:
        """Cifra dati con la chiave di sessione NTLM."""
        try:
            enc_data, signature = self._auth.encrypt(data)
            return signature + enc_data
        except Exception:
            return data


# ── CredSSP Handshake ─────────────────────────────────────────────────────────

class CredSSP:
    """
    CredSSP handshake su socket TLS (MS-CSSP).
    Scambia token NTLM poi invia credenziali cifrate.
    """

    def __init__(self, host: str, username: str, password: str, domain: str = ""):
        self._host     = host
        self._username = username
        self._password = password
        self._domain   = domain

    def handshake(self, ssl_sock) -> bool:
        targetspn = f"TERMSRV/{self._host}"
        auth = SSPIAuth(self._username, self._password, self._domain, targetspn)

        # Step 1: Negotiate
        neg = auth.get_negotiate()
        if not neg:
            raise ConnectionError("SSPI non ha prodotto NTLM Negotiate")
        _ts_send(ssl_sock, ts_request_encode(version=6, nego_token=neg))

        # Step 2: ricevi Challenge
        resp = _ts_recv(ssl_sock)
        parsed = ts_request_decode(resp)
        challenge = parsed.get("negoToken")
        if not challenge:
            raise ConnectionError("Server non ha inviato NTLM Challenge")

        # Step 3: Authenticate
        auth_tok = auth.get_authenticate(challenge)
        if not auth_tok:
            raise ConnectionError("SSPI non ha prodotto NTLM Authenticate")

        # Pubkey del server per pubKeyAuth
        try:
            pub_key = _get_server_pubkey(ssl_sock)
            pub_key_auth = auth.encrypt(pub_key)
        except Exception:
            pub_key_auth = None

        _ts_send(ssl_sock, ts_request_encode(
            version=6,
            nego_token=auth_tok,
            pub_key_auth=pub_key_auth))

        # Step 4: ricevi risposta pubkey (può essere skip su versioni vecchie)
        try:
            _ts_recv(ssl_sock)
        except Exception:
            pass

        # Step 5: invia credenziali cifrate
        creds     = ts_credentials_encode(self._username, self._password, self._domain)
        enc_creds = auth.encrypt(creds)
        _ts_send(ssl_sock, ts_request_encode(version=6, auth_info=enc_creds))
        return True


def _ts_send(sock, data: bytes):
    sock.sendall(data)


def _ts_recv(sock) -> bytes:
    """Legge un TSRequest DER-encoded dal socket TLS."""
    header = _sock_recv(sock, 2)
    tag, b1 = header[0], header[1]
    if b1 < 0x80:
        length = b1
    elif b1 == 0x81:
        length = _sock_recv(sock, 1)[0]
    else:
        nb = b1 & 0x7F
        length = int.from_bytes(_sock_recv(sock, nb), "big")
    body = _sock_recv(sock, length)
    return bytes([tag]) + _asn_len(length) + body


def _sock_recv(sock, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("Socket chiuso")
        buf += chunk
    return buf


def _get_server_pubkey(ssl_sock) -> bytes:
    """Ottieni la chiave pubblica DER dal certificato TLS del server."""
    try:
        cert_der = ssl_sock.getpeercert(binary_form=True)
        if not cert_der:
            return b""
        from cryptography.x509 import load_der_x509_certificate
        from cryptography.hazmat.primitives.serialization import (
            Encoding, PublicFormat)
        cert = load_der_x509_certificate(cert_der)
        return cert.public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
    except Exception:
        return b""
