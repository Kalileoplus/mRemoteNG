"""
RDP Client — sequenza di connessione completa (MS-RDPBCGR).
Gestisce: X.224 → TLS → NLA → MCS → Capabilities → Session.
"""
from __future__ import annotations
import socket
import ssl
import struct
import os
from typing import Callable, Optional

from .pdu import (
    tpkt_pack, tpkt_recv, x224_cr, x224_cc_parse,
    gcc_cs_core, gcc_cs_security, gcc_cs_net, gcc_cs_cluster,
    mcs_connect_initial, mcs_erect_domain, mcs_attach_user,
    mcs_channel_join, mcs_send_data,
    share_ctrl_header, share_data_header,
    PDU_TYPE_DEMAND_ACTIVE, PDU_TYPE_CONFIRM_ACTIVE,
    PDU_TYPE_DEACTIVATE_ALL, PDU_TYPE_DATA,
    PDUTYPE2_UPDATE, PDUTYPE2_CONTROL, PDUTYPE2_SYNCHRONIZE,
    PDUTYPE2_FONTMAP, PDUTYPE2_INPUT,
    STREAM_MED, STREAM_HI,
    MCS_ATTACH_USER_CONFIRM, MCS_CHANNEL_JOIN_CONFIRM,
    MCS_SEND_DATA_RESPONSE, CHANNEL_IO,
)
from .bitmap import parse_update_pdu


# ── Capabilities (minimal set per connessione funzionante) ───────────────────

def _build_capabilities(width: int, height: int) -> bytes:
    """Costruisce il set minimo di capability per il client."""

    def cap(type_id: int, data: bytes) -> bytes:
        return struct.pack("<HH", type_id, len(data) + 4) + data

    # CAPSTYPE_GENERAL (1)
    cap_general = cap(1, struct.pack("<HHHHHHHHH",
        0, 0x0200, 0x0200,
        0,          # protocolVersion
        0,          # pad2
        0,          # compressionTypes
        0x0040,     # extraFlags: FASTPATH_OUTPUT_SUPPORTED
        0, 0))

    # CAPSTYPE_BITMAP (2)
    cap_bitmap = cap(2, struct.pack("<HHHHHHHHHH",
        24,         # preferredBitsPerPixel
        1,          # receive1BitPerPixel
        1,          # receive4BitsPerPixel
        1,          # receive8BitsPerPixel
        width, height,
        0,          # desktopResizeFlag
        1,          # bitmapCompressionFlag
        0,          # highColorFlags
        0))         # drawingFlags

    # CAPSTYPE_ORDER (3) — minimal
    cap_order = cap(3, b"\x00" * 20 + struct.pack("<HHH", 1, 0, 0) + b"\x01" * 32 + b"\x00" * 4)

    # CAPSTYPE_POINTER (10)
    cap_ptr = cap(10, struct.pack("<HHH", 0, 0, 0))

    # CAPSTYPE_INPUT (13)
    cap_input = cap(13, struct.pack("<HHHIIH",
        0x0001,  # FASTPATH_INPUT_SUPPORTED
        0, 0, 0, 0, 0))

    # CAPSTYPE_VIRTUALCHANNEL (20)
    cap_vc = cap(20, struct.pack("<II", 1, 0))  # flags=1 (VCCAPS_COMPR_SC)

    caps = cap_general + cap_bitmap + cap_order + cap_ptr + cap_input + cap_vc
    return struct.pack("<H", 6) + caps  # numberCapabilities + padding


# ── Main RDP Client ──────────────────────────────────────────────────────────

class RDPClient:
    """
    Client RDP pure Python. Emette bitmap aggiornamenti via callback.
    Non threaded — da usare in un QThread.
    """

    def __init__(self,
                 host: str, port: int,
                 username: str, password: str, domain: str = "",
                 width: int = 1280, height: int = 720,
                 on_bitmap=None,       # callback(x,y,w,h,bgra_bytes)
                 on_connected=None,    # callback()
                 on_disconnected=None, # callback(msg)
                 on_error=None):       # callback(msg)
        self.host     = host
        self.port     = port
        self.username = username
        self.password = password
        self.domain   = domain
        self.width    = width
        self.height   = height

        self._on_bitmap      = on_bitmap
        self._on_connected   = on_connected
        self._on_disconnected = on_disconnected
        self._on_error       = on_error

        self._sock: Optional[ssl.SSLSocket] = None
        self._user_id  = 1004
        self._share_id = 0
        self._running  = False

    # ── connect ──────────────────────────────────────────────────────────────

    def connect(self):
        # ── TCP ───────────────────────────────────────────────────────────
        try:
            raw = socket.create_connection((self.host, self.port), timeout=15)
        except Exception as e:
            raise ConnectionError(f"Connessione TCP fallita a {self.host}:{self.port} — {e}")

        # ── X.224 Connection Request ──────────────────────────────────────
        try:
            raw.sendall(x224_cr(requested_protocols=3))
            cc_data  = tpkt_recv(raw)
            selected = x224_cc_parse(cc_data)
        except Exception as e:
            raise ConnectionError(f"Negoziazione X.224 fallita — {e}")

        # ── TLS ───────────────────────────────────────────────────────────
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode    = ssl.CERT_NONE
            self._sock = ctx.wrap_socket(raw, server_hostname=self.host)
        except Exception as e:
            raise ConnectionError(f"TLS handshake fallita — {e}")

        # ── NLA / CredSSP  (selectedProtocol & 2 = NLA richiesta) ────────
        # PROTOCOL_HYBRID=2, PROTOCOL_HYBRID_EX=8 entrambi richiedono NLA
        if selected & 0x0A:   # bit 1 (NLA) o bit 3 (NLA_EX)
            try:
                from .nla import CredSSP
                credssp = CredSSP(self.host, self.username, self.password, self.domain)
                credssp.handshake(self._sock)
            except Exception as e:
                raise ConnectionError(f"Autenticazione NLA fallita — {e}\n\n"
                                      "Verificare username, password e dominio.")

        # ── MCS Connect-Initial ───────────────────────────────────────────
        try:
            gcc_data = (gcc_cs_core(self.width, self.height) +
                        gcc_cs_security() +
                        gcc_cs_net("rdpdr", "rdpsnd", "cliprdr", "drdynvc") +
                        gcc_cs_cluster())
            self._sock.sendall(mcs_connect_initial(gcc_data))
            _tpkt_recv_skip(self._sock)
        except Exception as e:
            raise ConnectionError(f"MCS Connect fallito — {e}")

        # ── MCS channel setup ─────────────────────────────────────────────
        self._sock.sendall(mcs_erect_domain())
        self._sock.sendall(mcs_attach_user())
        _tpkt_recv_skip(self._sock)   # AttachUser Confirm

        for ch in [1003, 1004, 1005, 1006, 1007, 1008]:
            self._sock.sendall(mcs_channel_join(self._user_id, ch))
            _tpkt_recv_skip(self._sock)

        # ── Client Info ───────────────────────────────────────────────────
        self._send_client_info()

        # ── License exchange (skip) ───────────────────────────────────────
        for _ in range(4):
            try:
                pkt = tpkt_recv(self._sock)
                if len(pkt) > 3 and pkt[3] == PDU_TYPE_DATA:
                    break
            except Exception:
                break

        # ── Demand Active → Confirm Active → Finalize ─────────────────────
        self._wait_demand_active()
        self._send_confirm_active()
        self._send_finalize()

        self._running = True
        if self._on_connected:
            self._on_connected()

        # ── Main loop ─────────────────────────────────────────────────────
        self._recv_loop()

    def _send_client_info(self):
        uname = (self.username or "").encode("utf-16-le")
        pwd   = (self.password or "").encode("utf-16-le")
        dom   = (self.domain   or "").encode("utf-16-le")
        wdir  = b"\x00\x00"
        tz    = b"\x00" * 172

        info_pkt = struct.pack("<IHHHHHHHHH",
            0x00000003,  # flags: INFO_UNICODE | INFO_ENABLEWINDOWSKEY | INFO_MAXIMIZESHELL
            len(dom),
            len(uname),
            len(pwd),
            len(wdir),
            0x0409,      # keyboardLayout
            2600,        # clientBuild
            0x0001,      # keyboardType
            12,          # keyboardSubType (funckeys)
            0x0410,      # keyboardFunctionKey
        ) + b"\x00" * 64 + dom + b"\x00\x00" + uname + b"\x00\x00" + pwd + b"\x00\x00" + wdir + b"\x00\x00" + tz

        payload = struct.pack("<HH", 0, 0) + info_pkt   # secHeader (no encryption) + info
        self._sock.sendall(mcs_send_data(self._user_id, CHANNEL_IO, payload))

    def _wait_demand_active(self):
        for _ in range(20):
            try:
                pkt = tpkt_recv(self._sock)
                rdp = _strip_mcs_x224(pkt)
                if not rdp or len(rdp) < 6:
                    continue
                pdu_type = struct.unpack_from("<H", rdp, 2)[0] & 0xF
                if pdu_type == PDU_TYPE_DEMAND_ACTIVE:
                    self._share_id = struct.unpack_from("<I", rdp, 6)[0]
                    return
            except Exception:
                return

    def _send_confirm_active(self):
        caps = _build_capabilities(self.width, self.height)
        hdr  = struct.pack("<IHHH",
                           self._share_id,
                           0x03EA,    # originatorId = I/O channel
                           len(caps) + 4,
                           len(caps))
        pdu_data = hdr + caps
        rdp_hdr  = struct.pack("<HHI",
                               len(pdu_data) + 6,
                               PDU_TYPE_CONFIRM_ACTIVE | 0x10,
                               self._share_id)
        self._sock.sendall(mcs_send_data(self._user_id, CHANNEL_IO,
                                        struct.pack("<HH", 0, 0) + rdp_hdr + pdu_data))

    def _send_finalize(self):
        # Synchronize
        sync = self._rdp_data(PDUTYPE2_SYNCHRONIZE,
                              struct.pack("<HH", 1, self._user_id - 1001 + 1001))
        # Control (cooperate)
        ctrl1 = self._rdp_data(0x14, struct.pack("<HHII", 4, 0, 0, 0))
        # Control (request control)
        ctrl2 = self._rdp_data(0x14, struct.pack("<HHII", 1, 0, 0, 0))
        # Font list
        font  = self._rdp_data(0x27, struct.pack("<HHHH", 0, 0, 0x0003, 0x0032))
        for pkt in [sync, ctrl1, ctrl2, font]:
            self._sock.sendall(pkt)
        # Leggi Font Map dalla risposta
        for _ in range(5):
            try:
                tpkt_recv(self._sock)
            except Exception:
                break

    def _rdp_data(self, pdu_type2: int, data: bytes) -> bytes:
        inner = struct.pack("<IIBBHBBHH",
                            self._share_id,
                            0,
                            STREAM_MED,
                            len(data) + 4,
                            pdu_type2,
                            0, 0, 0, 0) + data
        hdr = struct.pack("<HHI", len(inner) + 6, PDU_TYPE_DATA | 0x10, self._share_id)
        return mcs_send_data(self._user_id, CHANNEL_IO,
                             struct.pack("<HH", 0, 0) + hdr + inner)

    # ── Receive loop ──────────────────────────────────────────────────────────

    def _recv_loop(self):
        while self._running:
            try:
                self._sock.settimeout(0.5)
                pkt = tpkt_recv(self._sock)
            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    if self._on_disconnected:
                        self._on_disconnected(str(e))
                return

            try:
                self._process_packet(pkt)
            except Exception:
                pass

    def _process_packet(self, pkt: bytes):
        rdp = _strip_mcs_x224(pkt)
        if not rdp or len(rdp) < 4:
            return

        # Fast-path update (senza header completo)
        if pkt[0] != 0x03 and pkt[0] & 0x03:
            self._handle_fastpath(pkt)
            return

        if len(rdp) < 6:
            return
        pdu_type = struct.unpack_from("<H", rdp, 2)[0] & 0xF

        if pdu_type == PDU_TYPE_DATA:
            if len(rdp) < 18:
                return
            pdu_type2 = rdp[17]
            payload   = rdp[18:]
            if pdu_type2 == PDUTYPE2_UPDATE:
                self._handle_update(payload)

        elif pdu_type == PDU_TYPE_DEACTIVATE_ALL:
            if self._on_disconnected:
                self._on_disconnected("Sessione terminata dal server.")
            self._running = False

    def _handle_fastpath(self, data: bytes):
        """Fast-path output PDUs (MS-RDPBCGR §2.2.9.1.2)."""
        if len(data) < 3:
            return
        fp_hdr = data[0]
        action = fp_hdr & 0x03
        if action != 0:
            return
        update_type = data[2] & 0x0F if len(data) > 2 else 0
        if update_type == 0x01:   # FASTPATH_UPDATETYPE_BITMAP
            self._handle_update(data[3:] if len(data) > 3 else b"")

    def _handle_update(self, payload: bytes):
        rects = parse_update_pdu(payload)
        if self._on_bitmap:
            for rect in rects:
                self._on_bitmap(*rect)

    # ── Input ─────────────────────────────────────────────────────────────────

    def send_key(self, scancode: int, flags: int = 0):
        """Invia evento tastiera (scancode + flags)."""
        inp = struct.pack("<HHHH", 1, flags, scancode, 0)
        self._send_input(0x0004, inp)   # INPUT_TYPE_SCANCODE

    def send_mouse(self, x: int, y: int, flags: int = 0):
        """Invia evento mouse."""
        inp = struct.pack("<HHHH", 0, flags, x, y)
        self._send_input(0x8001, inp)   # INPUT_TYPE_MOUSE

    def _send_input(self, input_type: int, input_data: bytes):
        payload = struct.pack("<HH", 1, 0) + struct.pack("<H", input_type) + b"\x00\x00" + input_data
        self._sock.sendall(self._rdp_data(PDUTYPE2_INPUT, payload))

    def disconnect(self):
        self._running = False
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass


# ── Helpers ───────────────────────────────────────────────────────────────────

def _tpkt_recv_skip(sock):
    try:
        tpkt_recv(sock)
    except Exception:
        pass


def _strip_mcs_x224(pkt: bytes) -> bytes:
    """Rimuove header X.224 Data (3 bytes) e MCS Send-Data-Response."""
    if len(pkt) < 3:
        return b""
    if pkt[0] == 0x02 and pkt[1] == 0xF0 and pkt[2] == 0x80:
        pkt = pkt[3:]
    if not pkt:
        return b""
    if (pkt[0] >> 2) == (0x6A >> 2):   # MCS_SEND_DATA_RESPONSE
        # Skip userId (2 bytes) + channelId (2 bytes) + flags (1) + length
        offset = 1
        user_id = struct.unpack_from(">H", pkt, offset)[0]; offset += 2
        chan_id = struct.unpack_from(">H", pkt, offset)[0]; offset += 2
        seg_flags = pkt[offset]; offset += 1
        # length encoding
        lb = pkt[offset]; offset += 1
        if lb & 0x80:
            length = ((lb & 0x7F) << 8) | pkt[offset]; offset += 1
        pkt = pkt[offset:]
    # Strip security header if present (4 bytes, flags == 0)
    if len(pkt) >= 4 and struct.unpack_from("<H", pkt, 0)[0] == 0:
        pkt = pkt[4:]
    return pkt
