; Inno Setup Script - Nexus Installer
; Genera: dist\Nexus_Setup.exe

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName=Nexus
AppVersion=1.0.0
AppPublisher=Kalileoplus
AppPublisherURL=https://github.com/Kalileoplus/mRemoteNG
AppSupportURL=https://github.com/Kalileoplus/mRemoteNG/issues
AppUpdatesURL=https://github.com/Kalileoplus/mRemoteNG/releases
DefaultDirName={autopf}\Nexus
DefaultGroupName=Nexus
AllowNoIcons=yes
LicenseFile=
OutputDir=dist
OutputBaseFilename=Nexus_Setup
SetupIconFile=PyMRemoteNG\icon.ico
WizardImageFile=
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\Nexus.exe
UninstallDisplayName=Nexus
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "italian";  MessagesFile: "compiler:Languages\Italian.isl"
Name: "english";  MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Crea icona sul Desktop";      GroupDescription: "Icone aggiuntive:"; Flags: checkedonce
Name: "startmenu";   Description: "Crea cartella nel menu Start"; GroupDescription: "Icone aggiuntive:"; Flags: checkedonce

[Files]
; Tutti i file dell'app buildata da PyInstaller
Source: "PyMRemoteNG\dist\Nexus\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Template configurazione connessioni
Source: "shared\confCons.xml.template"; DestDir: "{app}\shared"; Flags: ignoreversion

[Icons]
; Menu Start
Name: "{group}\Nexus";              Filename: "{app}\Nexus.exe"; Tasks: startmenu
Name: "{group}\Disinstalla Nexus";  Filename: "{uninstallexe}";  Tasks: startmenu
; Desktop
Name: "{autodesktop}\Nexus";        Filename: "{app}\Nexus.exe"; Tasks: desktopicon

[Registry]
; Registra l'app per "Programmi installati" nel Pannello di controllo
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\App Paths\Nexus.exe"; \
  ValueType: string; ValueName: ""; ValueData: "{app}\Nexus.exe"; Flags: uninsdeletekey

[Dirs]
; Crea cartella shared dove l'utente metterà il proprio confCons.xml
Name: "{app}\shared"

[Run]
Filename: "{app}\Nexus.exe"; \
  Description: "Avvia Nexus ora"; \
  Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Pulisce i file generati a runtime che non appartengono all'installer
Type: filesandordirs; Name: "{app}\shared"
Type: filesandordirs; Name: "{localappdata}\Nexus"
