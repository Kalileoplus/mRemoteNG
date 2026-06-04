"""
Generazione report CSV e HTML per audit, inventario e log sessioni.
"""
from __future__ import annotations
import csv
import io
import os
from datetime import datetime
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from core.models import ConnectionInfo
    from core.session_logger import SessionEvent


def connections_to_csv(connections: List["ConnectionInfo"]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Nome", "Hostname", "Porta", "Protocollo", "Username", "Gruppo", "Tag"])
    for c in connections:
        group = c.parent.name if c.parent else "Root"
        w.writerow([c.name, c.hostname, c.port,
                    c.protocol.value, c.username, group, c.tags])
    return buf.getvalue()


def sessions_to_csv(events: List["SessionEvent"]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Timestamp", "Tipo", "Utente", "Host", "Protocollo", "Dettaglio"])
    for e in events:
        w.writerow([e.ts, e.type, e.user, e.host, e.protocol, e.detail])
    return buf.getvalue()


def generate_html_report(connections: List["ConnectionInfo"],
                         events: List["SessionEvent"]) -> str:
    now = datetime.now().strftime("%d/%m/%Y %H:%M")

    proto_stats: dict = {}
    for c in connections:
        p = c.protocol.value
        proto_stats[p] = proto_stats.get(p, 0) + 1

    event_type_stats: dict = {}
    for e in events:
        event_type_stats[e.type] = event_type_stats.get(e.type, 0) + 1

    proto_rows = "".join(
        f"<tr><td>{p}</td><td>{n}</td></tr>"
        for p, n in sorted(proto_stats.items(), key=lambda x: -x[1])
    )
    conn_rows = "".join(
        f"<tr><td>{c.name}</td><td>{c.hostname}</td><td>{c.port}</td>"
        f"<td>{c.protocol.value}</td><td>{c.username}</td>"
        f"<td>{c.parent.name if c.parent else 'Root'}</td></tr>"
        for c in connections
    )
    event_rows = "".join(
        f"<tr><td>{e.ts}</td>"
        f"<td style='color:{_event_color(e.type)}'>{e.type}</td>"
        f"<td>{e.user}</td><td>{e.host}</td>"
        f"<td>{e.protocol}</td><td>{_esc(e.detail)}</td></tr>"
        for e in events[:500]
    )

    stat_cards = (
        f"<div class='stat'><div class='num'>{len(connections)}</div><div class='lbl'>Connessioni</div></div>"
        f"<div class='stat'><div class='num'>{len(events)}</div><div class='lbl'>Eventi log</div></div>"
        f"<div class='stat'><div class='num'>{len(proto_stats)}</div><div class='lbl'>Protocolli</div></div>"
        f"<div class='stat'><div class='num'>{event_type_stats.get('CONNECT',0)}</div><div class='lbl'>Connessioni aperte</div></div>"
        f"<div class='stat'><div class='num'>{event_type_stats.get('ERROR',0)}</div><div class='lbl' style='color:#EF5350'>Errori</div></div>"
    )

    return f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<title>PyMRemoteNG — Report {now}</title>
<style>
  body  {{ font-family: 'Segoe UI', sans-serif; background:#0D0D0D; color:#E8E8E8; margin:32px; }}
  h1   {{ color:#4EC94E; margin-bottom:4px; }}
  h2   {{ color:#5BA8E5; border-bottom:1px solid #2A2A2A; padding-bottom:6px; margin-top:32px; }}
  p.sub{{ color:#666; margin-top:0; font-size:13px; }}
  table{{ border-collapse:collapse; width:100%; margin-bottom:16px; font-size:13px; }}
  th   {{ background:#1A2A1A; color:#4EC94E; padding:8px 10px; text-align:left; }}
  td   {{ padding:6px 10px; border-bottom:1px solid #1A1A1A; }}
  tr:hover td{{ background:#141414; }}
  .stat{{ display:inline-block; background:#111; border:1px solid #222;
          border-radius:8px; padding:16px 20px; margin:6px; min-width:110px; text-align:center; }}
  .stat .num{{ font-size:2em; color:#5BA8E5; font-weight:bold; line-height:1; }}
  .stat .lbl{{ font-size:11px; color:#666; margin-top:4px; }}
  @media print{{ body{{ background:white; color:black; }} th{{ background:#eee; color:black; }} }}
</style>
</head>
<body>
<h1>PyMRemoteNG — Report Aziendale</h1>
<p class="sub">Generato il {now}</p>
<div>{stat_cards}</div>
<h2>Distribuzione Protocolli</h2>
<table>
  <tr><th>Protocollo</th><th>N. Connessioni</th></tr>
  {proto_rows}
</table>
<h2>Inventario Connessioni ({len(connections)})</h2>
<table>
  <tr><th>Nome</th><th>Hostname</th><th>Porta</th><th>Protocollo</th><th>Username</th><th>Gruppo</th></tr>
  {conn_rows}
</table>
<h2>Log Sessioni (ultimi {min(len(events),500)} di {len(events)})</h2>
<table>
  <tr><th>Timestamp</th><th>Tipo</th><th>Utente</th><th>Host</th><th>Protocollo</th><th>Dettaglio</th></tr>
  {event_rows}
</table>
</body>
</html>"""


def _event_color(t: str) -> str:
    return {"CONNECT": "#4EC94E", "DISCONNECT": "#FFC107",
            "ERROR": "#EF5350", "AUTH": "#5BA8E5"}.get(t, "#888")


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def save_file(content: str, path: str, encoding: str = "utf-8"):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    enc = "utf-8-sig" if path.endswith(".csv") else encoding
    with open(path, "w", encoding=enc, newline="" if path.endswith(".csv") else None) as f:
        f.write(content)
