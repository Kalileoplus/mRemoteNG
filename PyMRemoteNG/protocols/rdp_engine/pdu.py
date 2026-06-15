"""
RDP PDU helpers: TPKT, X.224, MCS structures.
Basato su MS-RDPBCGR (https://docs.microsoft.com/openspecs/windows_protocols/ms-rdpbcgr).
"""
import struct

# ── TPKT ────────────────────────────────────────────────────────────────────

def tpkt_pack(payload: bytes) -> bytes:
    length = len(payload) + 4
    return struct.pack(">BBH", 3, 0, length) + payload


def tpkt_recv(sock) -> bytes:
    """Legge un intero pacchetto TPKT dal socket."""
    header = _recv_exact(sock, 4)
    version, _, length = struct.unpack(">BBH", header)
    if version != 3:
        raise ValueError(f"TPKT version {version} non supportata")
    payload_len = length - 4
    return _recv_exact(sock, payload_len)


def _recv_exact(sock, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("Connessione chiusa inaspettatamente")
        buf += chunk
    return buf


# ── X.224 ───────────────────────────────────────────────────────────────────

X224_CR = 0xE0  # Connection Request
X224_CC = 0xD0  # Connection Confirm

def x224_cr(requested_protocols: int = 3, cookie: str = "") -> bytes:
    """X.224 Connection Request con RDP negotiation."""
    neg_req = struct.pack("<BBHI", 1, 0, 8, requested_protocols)
    if cookie:
        cookie_bytes = f"Cookie: mstshash={cookie}\r\n".encode()
    else:
        cookie_bytes = b""
    payload = cookie_bytes + neg_req
    hdr_len = len(payload) + 6
    x224_hdr = struct.pack(">BBBBBB",
                           hdr_len - 1, X224_CR,
                           0, 0,   # dst-ref
                           0, 0,   # src-ref
                           ) + b'\x00'   # class
    # Fix: X.224 header is 7 bytes for CR
    x224 = bytes([hdr_len - 1, X224_CR, 0, 0, 0, 0, 0]) + payload
    return tpkt_pack(x224)


def x224_cc_parse(data: bytes) -> int:
    """Parsa X.224 CC e ritorna selectedProtocol (0=Standard, 1=TLS, 2=NLA)."""
    if len(data) < 7:
        return 0
    # Byte 7+ contiene RDP_NEG_RSP se presente
    if len(data) >= 11 and data[7] == 2:
        selected = struct.unpack_from("<I", data, 11)[0]
        return selected
    return 1  # TLS default


# ── MCS GCC blobs (template basato su connessione standard) ─────────────────

# CS_CORE: Client Core Data (MS-RDPBCGR 2.2.1.3.2)
def gcc_cs_core(width: int, height: int, client_name: str = "Nexus") -> bytes:
    name_encoded = client_name.encode("utf-16-le")[:32]
    name_padded  = name_encoded.ljust(32, b"\x00")
    return struct.pack("<HHIHHHHHHHHHHH",
        0xC001,           # header type = CS_CORE
        158 + 4,          # header length (with type+len)
        0x00080004,       # version = RDP 5.1
        width, height,
        0xCA01,           # colorDepth = 8bpp (overridden by capabilities)
        0xAA03,           # SASSequence
        0x0409,           # keyboardLayout = EN-US
        2600,             # clientBuild
    ) + name_padded + struct.pack("<IHHHHHHIIHHII",
        4,                # keyboardType = IBM 101/102
        0,                # keyboardSubType
        12,               # keyboardFunctionKey
        0, 0,             # imeFileName (not used)
        0xCA01,           # postBeta2ColorDepth
        1,                # clientProductId
        0,                # serialNumber
        24,               # highColorDepth = 24bpp
        0x0007,           # supportedColorDepths = 15|16|24|32
        0x0007,           # earlyCapabilityFlags
        0, 0,             # clientDigProductId (not set)
    ) + bytes(64)         # clientDigProductId padding


def gcc_cs_security() -> bytes:
    return struct.pack("<HHII",
        0xC002, 12,       # CS_SEC header
        0,                # encryptionMethods = none (TLS used)
        0,                # extEncryptionMethods
    )


def gcc_cs_net(*channels: str) -> bytes:
    """CS_NET: richiesta canali virtuali."""
    channel_defs = b""
    for ch in channels:
        name = ch.encode().ljust(8, b"\x00")[:8]
        channel_defs += name + struct.pack("<I", 0x00000800)  # CHANNEL_OPTION_INITIALIZED
    return struct.pack("<HHI",
        0xC003, 4 + 12 * len(channels) + 4,
        len(channels),
    ) + channel_defs


def gcc_cs_cluster() -> bytes:
    return struct.pack("<HHI",
        0xC004, 12,
        0x0D,   # REDIRECTION_SUPPORTED | ServerSessionRedirectionVersionMask
        0,      # redirectedSessionID
    )


# ── Encoding minimo per MCS Connect-Initial ─────────────────────────────────

def ber_len(n: int) -> bytes:
    if n < 0x80:
        return bytes([n])
    elif n < 0x100:
        return bytes([0x81, n])
    else:
        return bytes([0x82, (n >> 8) & 0xFF, n & 0xFF])


def ber_octet_string(data: bytes) -> bytes:
    return b"\x04" + ber_len(len(data)) + data


def ber_bool(v: bool) -> bytes:
    return b"\x01\x01" + (b"\xFF" if v else b"\x00")


def ber_int(n: int, size: int = 1) -> bytes:
    val = n.to_bytes(size, "big")
    return b"\x02" + ber_len(len(val)) + val


def ber_seq(data: bytes) -> bytes:
    return b"\x30" + ber_len(len(data)) + data


def ber_app(tag: int, data: bytes) -> bytes:
    return bytes([0x60 | tag]) + ber_len(len(data)) + data


def _domain_params(max_channels: int = 34, max_users: int = 2,
                   max_tokens: int = 0, priority: int = 1,
                   max_pdu: int = 65535, max_height: int = 1,
                   service_count: int = 0, max_list: int = 0) -> bytes:
    return ber_seq(
        ber_int(max_channels, 3) +
        ber_int(max_users, 3) +
        ber_int(max_tokens, 3) +
        ber_int(priority, 3) +
        ber_int(max_pdu, 3) +
        ber_int(max_height, 3) +
        ber_int(service_count, 3) +
        ber_int(max_list, 3)
    )


def gcc_conference_request(user_data: bytes) -> bytes:
    """GCC ConferenceCreateRequest wrappato in H.221 key."""
    t124_oid = b"\x00\x05\x00\x14\x7c\x00\x01"
    h221_key = b"\x00\x44\x75\x63\x61"  # "Duca" — well-known H.221 key
    conference_name = ber_seq(ber_octet_string(b"1"))
    # PER encoding (simplified)
    gcc_pdu = t124_oid + ber_len(len(conference_name) + len(h221_key) + len(user_data) + 14) + conference_name + h221_key + ber_octet_string(user_data)
    return gcc_pdu


def mcs_connect_initial(gcc_user_data: bytes) -> bytes:
    """MCS Connect-Initial PDU (MS-RDPBCGR 2.2.1.3)."""
    gcc_req  = gcc_conference_request(gcc_user_data)
    user_dat = ber_octet_string(gcc_req)

    target  = _domain_params(34, 2, 0, 1, 65535, 1, 0, 0)
    minimum = _domain_params(1, 1, 1, 1, 512, 1, 0, 1)
    maximum = _domain_params(65535, 64002, 1000, 1, 4096, 1, 0, 1)

    inner = (
        ber_octet_string(b"\x01") +  # callingDomainSelector
        ber_octet_string(b"\x01") +  # calledDomainSelector
        ber_bool(True) +              # upwardFlag
        target + minimum + maximum +
        user_dat
    )
    mcs_body = ber_app(0x7F & 0x7F, inner)  # Application tag 0x7f
    # Actually: tag = 0x7F, sub-tag = 0x65 (= connect-initial)
    # Simplified: build direct
    mcs_pdu = b"\x7F\x65" + ber_len(len(inner)) + inner

    # Wrap in X.224 data + TPKT
    x224_data = b"\x02\xF0\x80"  # X.224 Data TPDU (DT)
    return tpkt_pack(x224_data + mcs_pdu)


# ── Canali MCS ───────────────────────────────────────────────────────────────

MCS_SEND_DATA_REQUEST  = 0x64
MCS_SEND_DATA_RESPONSE = 0x6A
MCS_ATTACH_USER_CONFIRM = 0x2E
MCS_CHANNEL_JOIN_CONFIRM = 0x3E

CHANNEL_IO = 1003   # I/O channel (main RDP data)
CHANNEL_GLOBAL = 1007

def mcs_erect_domain() -> bytes:
    return tpkt_pack(b"\x02\xF0\x80" + b"\x04\x01\x00\x01\x00")


def mcs_attach_user() -> bytes:
    return tpkt_pack(b"\x02\xF0\x80" + b"\x28")


def mcs_channel_join(user_id: int, channel_id: int) -> bytes:
    body = struct.pack(">BHH", 0x38, user_id - 1001, channel_id)
    return tpkt_pack(b"\x02\xF0\x80" + body)


def mcs_send_data(user_id: int, channel_id: int, payload: bytes,
                  flags: int = 0x70) -> bytes:
    header = struct.pack(">BHHB",
                         MCS_SEND_DATA_REQUEST,
                         user_id - 1001,
                         channel_id,
                         flags)
    length = len(payload)
    if length < 0x80:
        len_bytes = bytes([length])
    else:
        len_bytes = bytes([0x80 | (length >> 7), length & 0x7F])
    return tpkt_pack(b"\x02\xF0\x80" + header + len_bytes + payload)


# ── RDP Security / Encryption Layer ─────────────────────────────────────────

def rdp_sec_header(flags: int = 0) -> bytes:
    """Security header per dati non criptati (TLS mode)."""
    return struct.pack("<HH", flags, 0)  # securityHeader: flags, flagsHi


# ── Share Control Header ─────────────────────────────────────────────────────

PDU_TYPE_DEMAND_ACTIVE    = 0x11
PDU_TYPE_CONFIRM_ACTIVE   = 0x13
PDU_TYPE_DEACTIVATE_ALL   = 0x16
PDU_TYPE_DATA             = 0x17
PDU_TYPE_SERVER_REDIR     = 0x1A

def share_ctrl_header(pdu_type: int, share_id: int, stream_id: int = 0,
                      data: bytes = b"") -> bytes:
    total = len(data) + 6
    return struct.pack("<HHI", total, pdu_type | 0x10, share_id) + data


def share_data_header(share_id: int, pdu_type2: int, stream_id: int,
                      data: bytes) -> bytes:
    total = len(data) + 18
    return struct.pack("<HIBBHBBHH",
                       total,
                       share_id,
                       0,           # pad1
                       stream_id,
                       len(data) + 4,
                       pdu_type2,
                       0,           # compressedType
                       0,           # compressedLen
                       0,           # pad2
                       ) + data


# ── Costanti PDU_TYPE2 ───────────────────────────────────────────────────────

PDUTYPE2_UPDATE           = 0x02
PDUTYPE2_CONTROL          = 0x14
PDUTYPE2_POINTER          = 0x1B
PDUTYPE2_INPUT            = 0x1C
PDUTYPE2_SYNCHRONIZE      = 0x1F
PDUTYPE2_REFRESH_RECT     = 0x21
PDUTYPE2_PLAY_SOUND       = 0x22
PDUTYPE2_SUPPRESS_OUTPUT  = 0x23
PDUTYPE2_SHUTDOWN_REQUEST = 0x24
PDUTYPE2_SET_KEYBOARD_IME_STATUS = 0x29
PDUTYPE2_BITMAPCACHE_ERROR = 0x2B
PDUTYPE2_SET_KEYBOARD_INDICATORS = 0x2D
PDUTYPE2_BITMAPCACHE_ERROR_PDU = 0x2E
PDUTYPE2_SAVE_SESSION_INFO = 0x26
PDUTYPE2_FONTMAP          = 0x28

UPDATETYPE_BITMAP    = 0x0001
UPDATETYPE_PALETTE   = 0x0002

STREAM_LOW  = 1
STREAM_MED  = 2
STREAM_HI   = 4
