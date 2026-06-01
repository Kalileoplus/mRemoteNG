"""
Modello dati per le connessioni - equivalente di AbstractConnectionRecord + ConnectionInfo + ContainerInfo
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List
import uuid


class ProtocolType(str, Enum):
    RDP       = "RDP"
    VNC       = "VNC"
    SSH1      = "SSH1"
    SSH2      = "SSH2"
    Telnet    = "Telnet"
    Rlogin    = "Rlogin"
    RAW       = "RAW"
    HTTP      = "HTTP"
    HTTPS     = "HTTPS"
    PowerShell = "PowerShell"
    ARD       = "ARD"
    Terminal  = "Terminal"
    WSL       = "WSL"
    AnyDesk   = "AnyDesk"
    IntApp    = "IntApp"


class RDPResolution(str, Enum):
    SmartSize   = "SmartSize"
    FitToWindow = "FitToWindow"
    FullScreen  = "FullScreen"
    R1024x768   = "1024x768"
    R1280x1024  = "1280x1024"
    R1600x1200  = "1600x1200"
    R1920x1080  = "1920x1080"
    Custom      = "Custom"


class RDPColors(str, Enum):
    Colors8Bit  = "Colors8Bit"
    Colors15Bit = "Colors15Bit"
    Colors16Bit = "Colors16Bit"
    Colors24Bit = "Colors24Bit"
    Colors32Bit = "Colors32Bit"


class RDPAuthLevel(str, Enum):
    NoAuth      = "NoAuth"
    WarnOnConnect = "WarnOnConnect"
    RequireAuth = "RequireAuth"


class RDGatewayUsage(str, Enum):
    Never         = "Never"
    Always        = "Always"
    IfDirectFails = "IfDirectFails"


class RDPSound(str, Enum):
    DoNotPlay          = "DoNotPlay"
    BringToThisComputer = "BringToThisComputer"
    LeaveAtRemote      = "LeaveAtRemote"


class VNCEncoding(str, Enum):
    Raw     = "EncRaw"
    RRE     = "EncRRE"
    Hextile = "EncHextile"
    ZRLE    = "EncZRLE"


class VNCAuthMode(str, Enum):
    VNC  = "AuthVNC"
    Unix = "AuthUnix"


class VNCCompression(str, Enum):
    None_  = "CompNone"
    Jpeg   = "CompJpeg"
    Zlib   = "CompZlib"


class VNCProxyType(str, Enum):
    None_   = "ProxyNone"
    HTTP    = "ProxyHTTP"
    SOCKS5  = "ProxySOCKS5"


class ConnectionFrameColor(str, Enum):
    None_  = "None"
    Red    = "Red"
    Yellow = "Yellow"
    Green  = "Green"
    Blue   = "Blue"
    Purple = "Purple"


class TreeNodeType(str, Enum):
    Connection = "Connection"
    Container  = "Container"
    Root       = "Root"


@dataclass
class ConnectionInheritance:
    """Gestisce l'ereditarietà delle proprietà da parent container."""
    inherit_username:          bool = False
    inherit_password:          bool = False
    inherit_domain:            bool = False
    inherit_hostname:          bool = False
    inherit_port:              bool = False
    inherit_protocol:          bool = False
    inherit_resolution:        bool = False
    inherit_colors:            bool = False
    inherit_redirect_clipboard: bool = False
    inherit_redirect_drives:   bool = False
    inherit_redirect_printers: bool = False
    inherit_redirect_ports:    bool = False
    inherit_redirect_sound:    bool = False
    inherit_putty_session:     bool = False
    inherit_ssh_options:       bool = False


@dataclass
class ConnectionInfo:
    """Modello completo di una connessione - equivalente di ConnectionInfo.cs"""

    # Identificazione
    id:           str = field(default_factory=lambda: str(uuid.uuid4()))
    name:         str = "Nuova Connessione"
    description:  str = ""
    icon:         str = "mRemoteNG"
    panel:        str = "Generale"
    color:        str = ""
    tab_color:    str = ""
    frame_color:  ConnectionFrameColor = ConnectionFrameColor.None_
    favorite:     bool = False
    tags:         str = ""

    # Connessione
    hostname:     str = ""
    port:         int = 3389
    username:     str = ""
    password:     str = ""   # encrypted at rest
    domain:       str = ""

    # Protocollo
    protocol:     ProtocolType = ProtocolType.RDP
    putty_session: str = ""
    ssh_options:  str = ""
    opening_command: str = ""
    ssh_tunnel_name: str = ""

    # RDP
    rdp_version:              str = "Rdc10"
    use_console_session:      bool = False
    rdp_auth_level:           RDPAuthLevel = RDPAuthLevel.WarnOnConnect
    rdp_idle_timeout:         int = 0
    rdp_alert_idle:           bool = False
    load_balance_info:        str = ""
    use_cred_ssp:             bool = True
    use_restricted_admin:     bool = False
    use_rcg:                  bool = False
    use_vm_id:                bool = False
    vm_id:                    str = ""
    use_enhanced_mode:        bool = False
    rdp_start_program:        str = ""
    rdp_start_program_workdir: str = ""

    # RD Gateway
    rdg_usage:         RDGatewayUsage = RDGatewayUsage.Never
    rdg_hostname:      str = ""
    rdg_username:      str = ""
    rdg_password:      str = ""
    rdg_domain:        str = ""

    # Display / Resolution
    resolution:          RDPResolution = RDPResolution.SmartSize
    automatic_resize:    bool = True
    colors:              RDPColors = RDPColors.Colors32Bit
    cache_bitmaps:       bool = False
    display_wallpaper:   bool = False
    display_themes:      bool = False
    font_smoothing:      bool = False
    desktop_composition: bool = False
    disable_full_window_drag: bool = True
    disable_menu_animations:  bool = True
    disable_cursor_shadow:    bool = False
    disable_cursor_blinking:  bool = False

    # Redirect
    redirect_keys:         bool = False
    redirect_drives:       str = "None"
    redirect_drives_custom: str = ""
    redirect_printers:     bool = False
    redirect_clipboard:    bool = True
    redirect_ports:        bool = False
    redirect_smart_cards:  bool = False
    redirect_sound:        RDPSound = RDPSound.DoNotPlay
    sound_quality:         str = "Dynamic"
    redirect_audio_capture: bool = False

    # VNC
    vnc_compression: VNCCompression = VNCCompression.None_
    vnc_encoding:    VNCEncoding    = VNCEncoding.Hextile
    vnc_auth_mode:   VNCAuthMode    = VNCAuthMode.VNC
    vnc_proxy_type:  VNCProxyType   = VNCProxyType.None_
    vnc_proxy_ip:    str = ""
    vnc_proxy_port:  int = 0
    vnc_proxy_user:  str = ""
    vnc_proxy_pass:  str = ""
    vnc_colors:      str = "ColNormal"
    vnc_smart_size:  str = "SmartSAuto"
    vnc_view_only:   bool = False

    # HTTP
    rendering_engine: str = "EdgeChromium"

    # External tools
    pre_ext_app:  str = ""
    post_ext_app: str = ""
    ext_app:      str = ""

    # Misc
    mac_address:  str = ""
    user_field:   str = ""

    # Ereditarietà
    inheritance: ConnectionInheritance = field(default_factory=ConnectionInheritance)

    # Runtime (non persistiti)
    parent: Optional['ContainerInfo'] = field(default=None, repr=False, compare=False)
    is_container: bool = False

    def get_node_type(self) -> TreeNodeType:
        return TreeNodeType.Container if self.is_container else TreeNodeType.Connection

    def get_default_port(self) -> int:
        defaults = {
            ProtocolType.RDP: 3389,
            ProtocolType.VNC: 5900,
            ProtocolType.ARD: 5900,
            ProtocolType.SSH1: 22,
            ProtocolType.SSH2: 22,
            ProtocolType.Telnet: 23,
            ProtocolType.Rlogin: 513,
            ProtocolType.RAW: 23,
            ProtocolType.HTTP: 80,
            ProtocolType.HTTPS: 443,
            ProtocolType.PowerShell: 5985,
            ProtocolType.Terminal: 22,
        }
        return defaults.get(self.protocol, 0)

    def clone(self) -> 'ConnectionInfo':
        import copy
        cloned = copy.deepcopy(self)
        cloned.id = str(uuid.uuid4())
        cloned.name = f"{self.name} (copia)"
        cloned.parent = None
        return cloned

    def set_parent(self, parent: Optional['ContainerInfo']):
        if self.parent and self in self.parent.children:
            self.parent.children.remove(self)
        self.parent = parent
        if parent and self not in parent.children:
            parent.children.append(self)


@dataclass
class ContainerInfo(ConnectionInfo):
    """Cartella/gruppo di connessioni - equivalente di ContainerInfo.cs"""
    is_container: bool = True
    is_expanded:  bool = True
    children: List[ConnectionInfo] = field(default_factory=list)

    def get_node_type(self) -> TreeNodeType:
        return TreeNodeType.Container

    def add_child(self, child: ConnectionInfo):
        if child not in self.children:
            self.children.append(child)
            child.parent = self

    def remove_child(self, child: ConnectionInfo):
        if child in self.children:
            self.children.remove(child)
            child.parent = None

    def get_all_connections_recursive(self) -> List[ConnectionInfo]:
        result = []
        for child in self.children:
            if isinstance(child, ContainerInfo):
                result.extend(child.get_all_connections_recursive())
            else:
                result.append(child)
        return result

    def get_all_children_recursive(self) -> List[ConnectionInfo]:
        result = []
        for child in self.children:
            result.append(child)
            if isinstance(child, ContainerInfo):
                result.extend(child.get_all_children_recursive())
        return result


@dataclass
class RootNode(ContainerInfo):
    """Nodo radice dell'albero connessioni."""
    name: str = "Connessioni"
    is_container: bool = True

    def get_node_type(self) -> TreeNodeType:
        return TreeNodeType.Root


@dataclass
class CredentialRecord:
    """Record credenziali riutilizzabile."""
    id:       str = field(default_factory=lambda: str(uuid.uuid4()))
    title:    str = ""
    username: str = ""
    password: str = ""
    domain:   str = ""
