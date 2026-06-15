"""
Parser per file MobaXterm (.mxtsessions / .ini bookmarks).

Formato entry:
  Name=#TypeCode#ProtocolNum%Host%Port%Username%...
  es. #91#4%10.0.0.1%3389%user%...   (RDP)
      #109#0%10.0.0.1%22%%...         (SSH)
"""
from __future__ import annotations
import re
from typing import List, Tuple

from core.models import ConnectionInfo, ContainerInfo, ProtocolType


# MobaXterm protocol number → ProtocolType
_PROTO_MAP = {
    0:  ProtocolType.SSH2,
    1:  ProtocolType.Telnet,
    2:  ProtocolType.Rlogin,
    3:  ProtocolType.RAW,
    4:  ProtocolType.RDP,
    5:  ProtocolType.VNC,
    11: ProtocolType.HTTP,
}

_ENTRY_RE = re.compile(r'^#\d+#(\d+)%(.*)$')


def _parse_entry(name: str, value: str) -> ConnectionInfo | None:
    m = _ENTRY_RE.match(value)
    if not m:
        return None

    proto_num = int(m.group(1))
    fields = m.group(2).split('%')

    conn = ConnectionInfo()
    conn.name = name.strip()
    conn.protocol = _PROTO_MAP.get(proto_num, ProtocolType.SSH2)

    host = fields[0] if len(fields) > 0 else ""
    # Salta voci con placeholder tipo "IP?"
    if '?' in host:
        host = ""
    conn.hostname = host

    if len(fields) > 1 and fields[1] not in ('', '-1'):
        try:
            conn.port = int(fields[1])
        except ValueError:
            conn.port = conn.get_default_port()
    else:
        conn.port = conn.get_default_port()

    if len(fields) > 2 and fields[2]:
        # Per RDP il campo 2 contiene spesso "dominio\utente" o "utente@dominio"
        raw_user = fields[2]
        if '\\' in raw_user:
            domain, _, user = raw_user.partition('\\')
            conn.domain = domain
            conn.username = user
        else:
            conn.username = raw_user

    return conn


def parse_mobaxterm_file(filepath: str) -> List[Tuple[str, List[ConnectionInfo]]]:
    """
    Legge un file .mxtsessions e restituisce una lista di coppie
    (nome_cartella, [ConnectionInfo, ...]).
    Ogni sezione [Bookmarks...] diventa una cartella separata.
    """
    import os as _os
    abs_path = _os.path.realpath(filepath)
    # Accetta solo file nella home utente o in Temp (nessun path traversal / UNC share)
    home = _os.path.realpath(_os.path.expanduser("~"))
    temp = _os.path.realpath(_os.environ.get("TEMP", _os.path.join(home, "AppData", "Local", "Temp")))
    if not (abs_path.startswith(home + _os.sep) or abs_path.startswith(temp + _os.sep)):
        raise ValueError(f"Percorso file non consentito: {filepath}")
    # Verifica estensione
    if not abs_path.lower().endswith(('.mxtsessions', '.ini', '.txt')):
        raise ValueError("Tipo di file non supportato per l'importazione.")
    with open(abs_path, encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()

    sections: list[dict] = []
    current: dict | None = None

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith('[') and line.endswith(']'):
            current = {"subrep": "", "entries": []}
            sections.append(current)
        elif current is not None:
            if '=' in line:
                key, _, val = line.partition('=')
                key = key.strip()
                val = val.strip()
                if key == 'SubRep':
                    current["subrep"] = val
                elif key not in ('ImgNum',):
                    current["entries"].append((key, val))

    result: list[tuple[str, list[ConnectionInfo]]] = []

    for sec in sections:
        folder_name = sec["subrep"] or "MobaXterm Import"
        conns: list[ConnectionInfo] = []
        for name, value in sec["entries"]:
            c = _parse_entry(name, value)
            if c:
                conns.append(c)
        if conns:
            result.append((folder_name, conns))

    return result


def import_into_root(root, filepath: str) -> int:
    """
    Importa le connessioni nel RootNode fornito.
    Crea una ContainerInfo per ogni sezione trovata nel file.
    Ritorna il numero totale di connessioni importate.
    """
    from config.xml_parser import _rebuild_hierarchy_from_paths

    groups = parse_mobaxterm_file(filepath)
    total = 0
    for folder_name, conns in groups:
        # Cerca se esiste già una cartella con lo stesso nome
        existing = None
        for child in root.children:
            if isinstance(child, ContainerInfo) and child.name == folder_name:
                existing = child
                break
        if existing is None:
            existing = ContainerInfo()
            existing.name = folder_name
            root.add_child(existing)
        for c in conns:
            existing.add_child(c)
            total += 1

    # Ricostruisce la gerarchia da nomi tipo "TIBURTINO\ARSIAL"
    # in modo che ARSIAL diventi subito una sottocartella di TIBURTINO
    _rebuild_hierarchy_from_paths(root)
    return total
