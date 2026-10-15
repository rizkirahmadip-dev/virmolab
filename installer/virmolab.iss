; Installer VirmoLab (Inno Setup 6). Build: dev\rilis.py (memanggil ISCC dengan /DVersi=x.y.z)
#ifndef Versi
  #define Versi "0.0.0"
#endif
#define Akar ".."
; nama aplikasi sebelum 1.2.0 (hanya untuk membersihkan instalasi lama)
#define NamaLama "VirmoDock"

[Setup]
AppId={{6E3B2A51-8C1D-4E7F-9A42-5B0D7C9E1F38}
AppName=VirmoLab
AppVersion={#Versi}
AppVerName=VirmoLab {#Versi}
AppPublisher=apt. Rizki Rahmadi Pratama, M. Farm
AppComments=Aplikasi molecular docking desktop (AutoDock-GPU, Vina, AutoDock4)
VersionInfoVersion={#Versi}
DefaultDirName={autopf}\VirmoLab
DefaultGroupName=VirmoLab
DisableProgramGroupPage=yes
; tanpa hak admin secara bawaan (folder pengguna); bisa memilih "semua pengguna"
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#Akar}\rilis
OutputBaseFilename=VirmoLab-Setup-{#Versi}
SetupIconFile={#Akar}\virmolab\aset\virmolab.ico
UninstallDisplayIcon={app}\VirmoLab.exe
UninstallDisplayName=VirmoLab {#Versi}
WizardStyle=modern
WizardImageFile=wizard_besar_1x.bmp,wizard_besar_2x.bmp
WizardSmallImageFile=wizard_kecil_1x.bmp,wizard_kecil_2x.bmp
WizardImageStretch=no
WizardSizePercent=110
Compression=lzma2/max
SolidCompression=yes
LZMANumBlockThreads=4
#ifdef TandaTangan
; Penanda "virmolab" didefinisikan rilis.py lewat ISCC /S (build_tools\tanda_tangan.ps1); setup dan uninstaller
; ikut ditandatangani. Tanpa /DTandaTangan installer dibangun tanpa tanda tangan seperti sebelumnya.
SignTool=virmolab
SignedUninstaller=yes
#endif
CloseApplications=yes
ChangesAssociations=yes
ShowLanguageDialog=auto
; AppId sama dengan versi lama (sebelum 1.2.0) agar terpasang sebagai upgrade; folder lama dibersihkan di [Code]
UsePreviousAppDir=no

[Languages]
Name: "id"; MessagesFile: "Indonesian.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "assocbackup"; Description: "{cm:AssocFileExtension,VirmoLab,.vmdbackup}"; GroupDescription: "Asosiasi berkas:"
Name: "assocpdbqt"; Description: "{cm:AssocFileExtension,VirmoLab,.pdbqt}"; GroupDescription: "Asosiasi berkas:"; Flags: unchecked

[Files]
Source: "{#Akar}\dist\VirmoLab\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\VirmoLab"; Filename: "{app}\VirmoLab.exe"
Name: "{autoprograms}\VirmoLab - Panduan"; Filename: "{app}\_internal\docs\panduan.html"
Name: "{autodesktop}\VirmoLab"; Filename: "{app}\VirmoLab.exe"; Tasks: desktopicon

[InstallDelete]
; pintasan dari instalasi lama (sebelum 1.2.0)
Type: files; Name: "{autoprograms}\{#NamaLama}.lnk"
Type: files; Name: "{autoprograms}\{#NamaLama} - Panduan.lnk"
Type: files; Name: "{autodesktop}\{#NamaLama}.lnk"

[Registry]
; asosiasi berkas lama
Root: HKA; Subkey: "Software\Classes\{#NamaLama}.Cadangan"; ValueType: none; Flags: deletekey
Root: HKA; Subkey: "Software\Classes\{#NamaLama}.Struktur"; ValueType: none; Flags: deletekey
Root: HKA; Subkey: "Software\Classes\.pdbqt\OpenWithProgids"; ValueType: none; ValueName: "{#NamaLama}.Struktur"; Flags: deletevalue
Root: HKA; Subkey: "Software\Classes\.vmdbackup"; ValueType: string; ValueName: ""; ValueData: "VirmoLab.Cadangan"; Flags: uninsdeletevalue; Tasks: assocbackup
Root: HKA; Subkey: "Software\Classes\VirmoLab.Cadangan"; ValueType: string; ValueName: ""; ValueData: "Cadangan VirmoLab"; Flags: uninsdeletekey; Tasks: assocbackup
Root: HKA; Subkey: "Software\Classes\VirmoLab.Cadangan\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\VirmoLab.exe,0"; Tasks: assocbackup
Root: HKA; Subkey: "Software\Classes\VirmoLab.Cadangan\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\VirmoLab.exe"" ""%1"""; Tasks: assocbackup
Root: HKA; Subkey: "Software\Classes\.pdbqt\OpenWithProgids"; ValueType: string; ValueName: "VirmoLab.Struktur"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assocpdbqt
Root: HKA; Subkey: "Software\Classes\VirmoLab.Struktur"; ValueType: string; ValueName: ""; ValueData: "Struktur molekul (VirmoLab)"; Flags: uninsdeletekey; Tasks: assocpdbqt
Root: HKA; Subkey: "Software\Classes\VirmoLab.Struktur\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\VirmoLab.exe,0"; Tasks: assocpdbqt
Root: HKA; Subkey: "Software\Classes\VirmoLab.Struktur\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\VirmoLab.exe"" ""%1"""; Tasks: assocpdbqt

[Run]
Filename: "{app}\VirmoLab.exe"; Description: "{cm:LaunchProgram,VirmoLab}"; Flags: nowait postinstall skipifsilent

[Messages]
id.BeveledLabel=VirmoLab {#Versi}

[Code]
var
  FolderLama: String;

{ Folder instalasi lama (AppId sama) - dibaca sebelum entri uninstall ditimpa }
function InitializeSetup(): Boolean;
var
  Kunci: String;
begin
  Kunci := 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{6E3B2A51-8C1D-4E7F-9A42-5B0D7C9E1F38}_is1';
  if not RegQueryStringValue(HKCU, Kunci, 'Inno Setup: App Path', FolderLama) then
    RegQueryStringValue(HKLM, Kunci, 'Inno Setup: App Path', FolderLama);
  Result := True;
end;

{ Hapus folder lama hanya bila benar folder program lama (berisi exe lama) dan bukan folder tujuan baru }
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssPostInstall) and (FolderLama <> '') and
     (CompareText(RemoveBackslashUnlessRoot(FolderLama), RemoveBackslashUnlessRoot(ExpandConstant('{app}'))) <> 0) and
     FileExists(AddBackslash(FolderLama) + '{#NamaLama}.exe') then
    DelTree(FolderLama, True, True, True);
end;
