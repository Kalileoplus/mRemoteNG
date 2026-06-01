"""
Parser e writer per confCons.xml (formato mRemoteNG v2.8)
"""
from __future__ import annotations
import xml.etree.ElementTree as ET
from typing import Optional
from core.models import (
    ConnectionInfo, ContainerInfo, RootNode,
    ProtocolType, RDPResolution, RDPColors, RDPAuthLevel,
    RDGatewayUsage, RDPSound, VNCEncoding, VNCAuthMode,
    VNCCompression, VNCProxyType, ConnectionFrameColor,
    ConnectionInheritance
)


def _get(attr: dict, key: str, default="") -> str:
    return attr.get(key, default)


def _getb(attr: dict, key: str, default: bool = False) -> bool:
    return attr.get(key, str(default)).lower() == "true"


def _geti(attr: dict, key: str, default: int = 0) -> int:
    try:
        return int(attr.get(key, default))
    except (ValueError, TypeError):
        return default


def _parse_node(element: ET.Element, parent=None) -> Optional[ConnectionInfo]:
    a = element.attrib
    node_type = a.get("Type", "Connection")

    if node_type == "Container":
        node = ContainerInfo()
        node.is_expanded = _getb(a, "Expanded", True)
    else:
        node = ConnectionInfo()

    node.name        = _get(a, "Name", "Senza nome")
    node.description = _get(a, "Descr", "")
    node.icon        = _get(a, "Icon", "mRemoteNG")
    node.panel       = _get(a, "Panel", "Generale")
    node.color       = _get(a, "Color", "")
    node.tab_color   = _get(a, "TabColor", "")
    node.favorite    = _getb(a, "Favorite", False)
    node.tags        = _get(a, "Tags", "")

    # Connessione
    node.hostname = _get(a, "Hostname", "")
    node.port     = _geti(a, "Port", 3389)
    node.username = _get(a, "Username", "")
    node.password = _get(a, "Password", "")   # già cifrato
    node.domain   = _get(a, "Domain", "")

    # Protocollo
    proto_str = _get(a, "Protocol", "RDP")
    try:
        node.protocol = ProtocolType(proto_str)
    except ValueError:
        node.protocol = ProtocolType.RDP

    node.putty_session    = _get(a, "PuttySession", "")
    node.ssh_options      = _get(a, "SSHOptions", "")
    node.opening_command  = _get(a, "OpeningCommand", "")
    node.ssh_tunnel_name  = _get(a, "SSHTunnelConnectionName", "")
    node.ext_app          = _get(a, "ExtApp", "")

    # RDP
    node.rdp_version          = _get(a, "RDPVersion", "Rdc10")
    node.use_console_session  = _getb(a, "UseConsoleSession", False)
    node.rdp_idle_timeout     = _geti(a, "RDPMinutesToIdleTimeout", 0)
    node.rdp_alert_idle       = _getb(a, "RDPAlertIdleTimeout", False)
    node.load_balance_info    = _get(a, "LoadBalanceInfo", "")
    node.use_cred_ssp         = _getb(a, "UseCredSsp", True)
    node.use_restricted_admin = _getb(a, "UseRestrictedAdmin", False)
    node.rdp_start_program    = _get(a, "RDPStartProgram", "")
    node.rdp_start_program_workdir = _get(a, "RDPStartProgramWorkDir", "")
    node.vm_id                = _get(a, "VmId", "")
    node.use_vm_id            = _getb(a, "UseVmId", False)
    node.use_enhanced_mode    = _getb(a, "UseEnhancedMode", False)

    try:
        node.rdp_auth_level = RDPAuthLevel(_get(a, "RDPAuthenticationLevel", "WarnOnConnect"))
    except ValueError:
        node.rdp_auth_level = RDPAuthLevel.WarnOnConnect

    # RD Gateway
    try:
        node.rdg_usage = RDGatewayUsage(_get(a, "RDGatewayUsageMethod", "Never"))
    except ValueError:
        node.rdg_usage = RDGatewayUsage.Never
    node.rdg_hostname = _get(a, "RDGatewayHostname", "")
    node.rdg_username = _get(a, "RDGatewayUsername", "")
    node.rdg_password = _get(a, "RDGatewayPassword", "")
    node.rdg_domain   = _get(a, "RDGatewayDomain", "")

    # Display
    try:
        node.resolution = RDPResolution(_get(a, "Resolution", "SmartSize"))
    except ValueError:
        node.resolution = RDPResolution.SmartSize
    node.automatic_resize       = _getb(a, "AutomaticResize", True)
    try:
        node.colors = RDPColors(_get(a, "Colors", "Colors32Bit"))
    except ValueError:
        node.colors = RDPColors.Colors32Bit
    node.cache_bitmaps           = _getb(a, "CacheBitmaps", False)
    node.display_wallpaper        = _getb(a, "DisplayWallpaper", False)
    node.display_themes           = _getb(a, "DisplayThemes", False)
    node.font_smoothing           = _getb(a, "EnableFontSmoothing", False)
    node.desktop_composition      = _getb(a, "EnableDesktopComposition", False)
    node.disable_full_window_drag = _getb(a, "DisableFullWindowDrag", True)
    node.disable_menu_animations  = _getb(a, "DisableMenuAnimations", True)
    node.disable_cursor_shadow    = _getb(a, "DisableCursorShadow", False)
    node.disable_cursor_blinking  = _getb(a, "DisableCursorBlinking", False)

    # Redirect
    node.redirect_drives   = _get(a, "RedirectDiskDrives", "None")
    node.redirect_printers = _getb(a, "RedirectPrinters", False)
    node.redirect_clipboard = _getb(a, "RedirectClipboard", True)
    node.redirect_ports    = _getb(a, "RedirectPorts", False)
    node.redirect_smart_cards = _getb(a, "RedirectSmartCards", False)
    node.redirect_keys     = _getb(a, "RedirectKeys", False)
    try:
        node.redirect_sound = RDPSound(_get(a, "RedirectSound", "DoNotPlay"))
    except ValueError:
        node.redirect_sound = RDPSound.DoNotPlay
    node.redirect_audio_capture = _getb(a, "RedirectAudioCapture", False)

    # VNC
    try:
        node.vnc_compression = VNCCompression(_get(a, "VNCCompression", "CompNone"))
    except ValueError:
        node.vnc_compression = VNCCompression.None_
    try:
        node.vnc_encoding = VNCEncoding(_get(a, "VNCEncoding", "EncHextile"))
    except ValueError:
        node.vnc_encoding = VNCEncoding.Hextile
    try:
        node.vnc_auth_mode = VNCAuthMode(_get(a, "VNCAuthMode", "AuthVNC"))
    except ValueError:
        node.vnc_auth_mode = VNCAuthMode.VNC
    try:
        node.vnc_proxy_type = VNCProxyType(_get(a, "VNCProxyType", "ProxyNone"))
    except ValueError:
        node.vnc_proxy_type = VNCProxyType.None_
    node.vnc_proxy_ip   = _get(a, "VNCProxyIP", "")
    node.vnc_proxy_port = _geti(a, "VNCProxyPort", 0)
    node.vnc_proxy_user = _get(a, "VNCProxyUsername", "")
    node.vnc_proxy_pass = _get(a, "VNCProxyPassword", "")
    node.vnc_colors     = _get(a, "VNCColors", "ColNormal")
    node.vnc_smart_size = _get(a, "VNCSmartSizeMode", "SmartSAuto")
    node.vnc_view_only  = _getb(a, "VNCViewOnly", False)

    # HTTP
    node.rendering_engine = _get(a, "RenderingEngine", "EdgeChromium")

    # External tools / misc
    node.pre_ext_app  = _get(a, "PreExtApp", "")
    node.post_ext_app = _get(a, "PostExtApp", "")
    node.mac_address  = _get(a, "MacAddress", "")
    node.user_field   = _get(a, "UserField", "")

    # Inheritance
    inh = node.inheritance
    inh.inherit_username    = _getb(a, "InheritUsername", False)
    inh.inherit_password    = _getb(a, "InheritPassword", False)
    inh.inherit_domain      = _getb(a, "InheritDomain", False)
    inh.inherit_hostname    = _getb(a, "InheritHostname", False)
    inh.inherit_port        = _getb(a, "InheritPort", False)
    inh.inherit_protocol    = _getb(a, "InheritProtocol", False)
    inh.inherit_resolution  = _getb(a, "InheritResolution", False)
    inh.inherit_colors      = _getb(a, "InheritColors", False)
    inh.inherit_redirect_clipboard = _getb(a, "InheritRedirectClipboard", False)
    inh.inherit_redirect_drives    = _getb(a, "InheritRedirectDiskDrives", False)
    inh.inherit_redirect_printers  = _getb(a, "InheritRedirectPrinters", False)
    inh.inherit_redirect_ports     = _getb(a, "InheritRedirectPorts", False)
    inh.inherit_redirect_sound     = _getb(a, "InheritRedirectSound", False)
    inh.inherit_putty_session      = _getb(a, "InheritPuttySession", False)
    inh.inherit_ssh_options        = _getb(a, "InheritSSHOptions", False)

    node.parent = parent

    # Figli (solo per container)
    if isinstance(node, ContainerInfo):
        for child_elem in element:
            child = _parse_node(child_elem, node)
            if child:
                node.children.append(child)

    return node


def load_connections(filepath: str) -> RootNode:
    """Carica confCons.xml e restituisce il RootNode."""
    root = RootNode()
    try:
        tree = ET.parse(filepath)
        xml_root = tree.getroot()
        root.name = xml_root.attrib.get("Name", "Connessioni")
        for elem in xml_root:
            child = _parse_node(elem, root)
            if child:
                root.children.append(child)
    except FileNotFoundError:
        pass
    except ET.ParseError as e:
        print(f"Errore parsing XML: {e}")
    return root


def _node_to_element(node: ConnectionInfo) -> ET.Element:
    node_type = "Container" if isinstance(node, ContainerInfo) else "Connection"
    elem = ET.Element("Node")
    a = elem.attrib

    a["Name"]     = node.name
    a["Type"]     = node_type
    a["Descr"]    = node.description
    a["Icon"]     = node.icon
    a["Panel"]    = node.panel
    a["Color"]    = node.color
    a["TabColor"] = node.tab_color
    a["Favorite"] = str(node.favorite)
    a["Tags"]     = node.tags

    if isinstance(node, ContainerInfo):
        a["Expanded"] = str(node.is_expanded)

    a["Hostname"]        = node.hostname
    a["Port"]            = str(node.port)
    a["Username"]        = node.username
    a["Password"]        = node.password
    a["Domain"]          = node.domain
    a["Protocol"]        = node.protocol.value
    a["PuttySession"]    = node.putty_session
    a["SSHOptions"]      = node.ssh_options
    a["OpeningCommand"]  = node.opening_command
    a["SSHTunnelConnectionName"] = node.ssh_tunnel_name
    a["ExtApp"]          = node.ext_app

    # RDP
    a["RDPVersion"]            = node.rdp_version
    a["UseConsoleSession"]     = str(node.use_console_session)
    a["RDPMinutesToIdleTimeout"] = str(node.rdp_idle_timeout)
    a["RDPAlertIdleTimeout"]   = str(node.rdp_alert_idle)
    a["LoadBalanceInfo"]       = node.load_balance_info
    a["UseCredSsp"]            = str(node.use_cred_ssp)
    a["UseRestrictedAdmin"]    = str(node.use_restricted_admin)
    a["RDPAuthenticationLevel"] = node.rdp_auth_level.value
    a["RDPStartProgram"]       = node.rdp_start_program
    a["RDPStartProgramWorkDir"] = node.rdp_start_program_workdir

    # RD Gateway
    a["RDGatewayUsageMethod"]  = node.rdg_usage.value
    a["RDGatewayHostname"]     = node.rdg_hostname
    a["RDGatewayUsername"]     = node.rdg_username
    a["RDGatewayPassword"]     = node.rdg_password
    a["RDGatewayDomain"]       = node.rdg_domain

    # Display
    a["Resolution"]           = node.resolution.value
    a["AutomaticResize"]      = str(node.automatic_resize)
    a["Colors"]               = node.colors.value
    a["CacheBitmaps"]         = str(node.cache_bitmaps)
    a["DisplayWallpaper"]     = str(node.display_wallpaper)
    a["DisplayThemes"]        = str(node.display_themes)
    a["EnableFontSmoothing"]  = str(node.font_smoothing)
    a["EnableDesktopComposition"] = str(node.desktop_composition)

    # Redirect
    a["RedirectDiskDrives"]   = node.redirect_drives
    a["RedirectPrinters"]     = str(node.redirect_printers)
    a["RedirectClipboard"]    = str(node.redirect_clipboard)
    a["RedirectPorts"]        = str(node.redirect_ports)
    a["RedirectSmartCards"]   = str(node.redirect_smart_cards)
    a["RedirectKeys"]         = str(node.redirect_keys)
    a["RedirectSound"]        = node.redirect_sound.value
    a["RedirectAudioCapture"] = str(node.redirect_audio_capture)

    # VNC
    a["VNCCompression"]    = node.vnc_compression.value
    a["VNCEncoding"]       = node.vnc_encoding.value
    a["VNCAuthMode"]       = node.vnc_auth_mode.value
    a["VNCProxyType"]      = node.vnc_proxy_type.value
    a["VNCProxyIP"]        = node.vnc_proxy_ip
    a["VNCProxyPort"]      = str(node.vnc_proxy_port)
    a["VNCProxyUsername"]  = node.vnc_proxy_user
    a["VNCProxyPassword"]  = node.vnc_proxy_pass
    a["VNCColors"]         = node.vnc_colors
    a["VNCSmartSizeMode"]  = node.vnc_smart_size
    a["VNCViewOnly"]       = str(node.vnc_view_only)

    # HTTP
    a["RenderingEngine"]   = node.rendering_engine

    # Misc
    a["PreExtApp"]         = node.pre_ext_app
    a["PostExtApp"]        = node.post_ext_app
    a["MacAddress"]        = node.mac_address
    a["UserField"]         = node.user_field

    # Inheritance
    inh = node.inheritance
    a["InheritUsername"]          = str(inh.inherit_username)
    a["InheritPassword"]          = str(inh.inherit_password)
    a["InheritDomain"]            = str(inh.inherit_domain)
    a["InheritHostname"]          = str(inh.inherit_hostname)
    a["InheritPort"]              = str(inh.inherit_port)
    a["InheritProtocol"]          = str(inh.inherit_protocol)
    a["InheritResolution"]        = str(inh.inherit_resolution)
    a["InheritColors"]            = str(inh.inherit_colors)
    a["InheritRedirectClipboard"] = str(inh.inherit_redirect_clipboard)
    a["InheritRedirectDiskDrives"] = str(inh.inherit_redirect_drives)
    a["InheritRedirectPrinters"]  = str(inh.inherit_redirect_printers)
    a["InheritRedirectPorts"]     = str(inh.inherit_redirect_ports)
    a["InheritRedirectSound"]     = str(inh.inherit_redirect_sound)
    a["InheritPuttySession"]      = str(inh.inherit_putty_session)
    a["InheritSSHOptions"]        = str(inh.inherit_ssh_options)

    if isinstance(node, ContainerInfo):
        for child in node.children:
            elem.append(_node_to_element(child))

    return elem


def save_connections(root_node: RootNode, filepath: str):
    """Salva l'albero connessioni in confCons.xml."""
    xml_root = ET.Element("Connections")
    xml_root.attrib["Name"]          = root_node.name
    xml_root.attrib["Export"]        = "False"
    xml_root.attrib["ConfVersion"]   = "2.8"
    xml_root.attrib["EncryptionEngine"] = "AES"
    xml_root.attrib["BlockCipherMode"]  = "GCM"
    xml_root.attrib["KdfIterations"]    = "1000"
    xml_root.attrib["FullFileEncryption"] = "False"

    for child in root_node.children:
        xml_root.append(_node_to_element(child))

    _indent_xml(xml_root)
    tree = ET.ElementTree(xml_root)
    ET.indent(tree, space="    ")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="utf-8"?>\n')
        tree.write(f, encoding="unicode", xml_declaration=False)


def _indent_xml(elem: ET.Element, level: int = 0):
    indent = "\n" + "    " * level
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = indent + "    "
        if not elem.tail or not elem.tail.strip():
            elem.tail = indent
        for child in elem:
            _indent_xml(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = indent
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = indent
