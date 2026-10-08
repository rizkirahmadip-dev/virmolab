; Installer VirmoDock (Inno Setup 6). Build: dev\rilis.py (memanggil ISCC dengan /DVersi=x.y.z)
#ifndef Versi
  #define Versi "0.0.0"
#endif
#define Akar ".."

[Setup]
AppId={{6E3B2A51-8C1D-4E7F-9A42-5B0D7C9E1F38}
AppName=VirmoDock
AppVersion={#Versi}
AppVerName=VirmoDock {#Versi}
AppPublisher=apt. Rizki Rahmadi Pratama, M. Farm
AppComments=Aplikasi molecular docking desktop (AutoDock-GPU, Vina, AutoDock4)
VersionInfoVersion={#Versi}
DefaultDirName={autopf}\VirmoDock
DefaultGroupName=VirmoDock
DisableProgramGroupPage=yes
; tanpa hak admin secara bawaan (folder pengguna); bisa memilih "semua pengguna"
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#Akar}\rilis
OutputBaseFilename=VirmoDock-Setup-{#Versi}
SetupIconFile={#Akar}\virmodock\aset\virmodock.ico
UninstallDisplayIcon={app}\VirmoDock.exe
UninstallDisplayName=VirmoDock {#Versi}
WizardStyle=modern
WizardImageFile=wizard_besar_1x.bmp,wizard_besar_2x.bmp
WizardSmallImageFile=wizard_kecil_1x.bmp,wizard_kecil_2x.bmp
WizardImageStretch=no
WizardSizePercent=110
Compression=lzma2/max
SolidCompression=yes
LZMANumBlockThreads=4
CloseApplications=yes
ChangesAssociations=yes
ShowLanguageDialog=auto

[Languages]
Name: "id"; MessagesFile: "Indonesian.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "assocbackup"; Description: "{cm:AssocFileExtension,VirmoDock,.vmdbackup}"; GroupDescription: "Asosiasi berkas:"
Name: "assocpdbqt"; Description: "{cm:AssocFileExtension,VirmoDock,.pdbqt}"; GroupDescription: "Asosiasi berkas:"; Flags: unchecked

[Files]
Source: "{#Akar}\dist\VirmoDock\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\VirmoDock"; Filename: "{app}\VirmoDock.exe"
Name: "{autoprograms}\VirmoDock - Panduan"; Filename: "{app}\_internal\docs\panduan.html"
Name: "{autodesktop}\VirmoDock"; Filename: "{app}\VirmoDock.exe"; Tasks: desktopicon

[Registry]
Root: HKA; Subkey: "Software\Classes\.vmdbackup"; ValueType: string; ValueName: ""; ValueData: "VirmoDock.Cadangan"; Flags: uninsdeletevalue; Tasks: assocbackup
Root: HKA; Subkey: "Software\Classes\VirmoDock.Cadangan"; ValueType: string; ValueName: ""; ValueData: "Cadangan VirmoDock"; Flags: uninsdeletekey; Tasks: assocbackup
Root: HKA; Subkey: "Software\Classes\VirmoDock.Cadangan\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\VirmoDock.exe,0"; Tasks: assocbackup
Root: HKA; Subkey: "Software\Classes\VirmoDock.Cadangan\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\VirmoDock.exe"" ""%1"""; Tasks: assocbackup
Root: HKA; Subkey: "Software\Classes\.pdbqt\OpenWithProgids"; ValueType: string; ValueName: "VirmoDock.Struktur"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assocpdbqt
Root: HKA; Subkey: "Software\Classes\VirmoDock.Struktur"; ValueType: string; ValueName: ""; ValueData: "Struktur molekul (VirmoDock)"; Flags: uninsdeletekey; Tasks: assocpdbqt
Root: HKA; Subkey: "Software\Classes\VirmoDock.Struktur\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\VirmoDock.exe,0"; Tasks: assocpdbqt
Root: HKA; Subkey: "Software\Classes\VirmoDock.Struktur\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\VirmoDock.exe"" ""%1"""; Tasks: assocpdbqt

[Run]
Filename: "{app}\VirmoDock.exe"; Description: "{cm:LaunchProgram,VirmoDock}"; Flags: nowait postinstall skipifsilent

[Messages]
id.BeveledLabel=VirmoDock {#Versi}
