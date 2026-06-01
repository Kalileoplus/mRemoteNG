; Inno Setup Script - PyMRemoteNG Installer
; Genera: dist\PyMRemoteNG_Setup.exe

[Setup]
AppId={{3F8A7B2C-1D4E-4F6A-8B9C-0D1E2F3A4B5C}
AppName=PyMRemoteNG
AppVersion=1.0.0
AppPublisher=Kalileoplus
AppPublisherURL=https://github.com/Kalileoplus/mRemoteNG
AppSupportURL=https://github.com/Kalileoplus/mRemoteNG/issues
AppUpdatesURL=https://github.com/Kalileoplus/mRemoteNG/releases
DefaultDirName={autopf}\PyMRemoteNG
DefaultGroupName=PyMRemoteNG
AllowNoIcons=yes
LicenseFile=
OutputDir=dist
OutputBaseFilename=PyMRemoteNG_Setup
SetupIconFile=PyMRemoteNG\icon.ico
WizardImageFile=
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\PyMRemoteNG.exe
UninstallDisplayName=PyMRemoteNG
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "italian";  MessagesFile: "compiler:Languages\Italian.isl"
Name: "english";  MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Crea icona sul Desktop";     GroupDescription: "Icone aggiuntive:"; Flags: checkedonce
Name: "startmenu";   Description: "Crea cartella nel menu Start"; GroupDescription: "Icone aggiuntive:"; Flags: checkedonce

[Files]
; Tutti i file dell'app buildata da PyInstaller
Source: "PyMRemoteNG\dist\PyMRemoteNG\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Template configurazione connessioni
Source: "shared\confCons.xml.template"; DestDir: "{app}\shared"; Flags: ignoreversion

[Icons]
; Menu Start
Name: "{group}\PyMRemoteNG";                       Filename: "{app}\PyMRemoteNG.exe"; Tasks: startmenu
Name: "{group}\Disinstalla PyMRemoteNG";           Filename: "{uninstallexe}";        Tasks: startmenu
; Desktop
Name: "{autodesktop}\PyMRemoteNG";                 Filename: "{app}\PyMRemoteNG.exe"; Tasks: desktopicon

[Registry]
; Registra l'app per "Programmi installati" nel Pannello di controllo
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\App Paths\PyMRemoteNG.exe"; \
  ValueType: string; ValueName: ""; ValueData: "{app}\PyMRemoteNG.exe"; Flags: uninsdeletekey

[Dirs]
; Crea cartella shared dove l'utente metterà il proprio confCons.xml
Name: "{app}\shared"

[Run]
Filename: "{app}\PyMRemoteNG.exe"; \
  Description: "Avvia PyMRemoteNG ora"; \
  Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Pulisce i file generati a runtime che non appartengono all'installer
Type: filesandordirs; Name: "{app}\shared"
Type: filesandordirs; Name: "{localappdata}\PyMRemoteNG"
