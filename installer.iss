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
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
; Icona desktop sempre selezionata di default
Name: "desktopicon"; Description: "Crea icona sul Desktop"; Flags: checked

[Files]
; App buildata da PyInstaller (standalone, non richiede Python)
Source: "PyMRemoteNG\dist\Nexus\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Template configurazione connessioni
Source: "shared\confCons.xml.template"; DestDir: "{app}\shared"; Flags: ignoreversion

[Icons]
; Desktop (sempre creato)
Name: "{autodesktop}\Nexus"; Filename: "{app}\Nexus.exe"; IconFilename: "{app}\Nexus.exe"; Tasks: desktopicon
; Menu Start
Name: "{group}\Nexus";             Filename: "{app}\Nexus.exe"
Name: "{group}\Disinstalla Nexus"; Filename: "{uninstallexe}"

[Registry]
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\App Paths\Nexus.exe"; \
  ValueType: string; ValueName: ""; ValueData: "{app}\Nexus.exe"; Flags: uninsdeletekey

[Dirs]
Name: "{app}\shared"

[Run]
Filename: "{app}\Nexus.exe"; \
  Description: "Avvia Nexus ora"; \
  Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\shared"
Type: filesandordirs; Name: "{localappdata}\Nexus"
