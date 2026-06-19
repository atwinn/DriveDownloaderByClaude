; Inno Setup script — builds Setup.exe from the PyInstaller output.
; Compile on Windows after build_win.ps1:
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
; Result: Output\DriveDownloader-Setup.exe

#define AppName "Drive Downloader"
#define AppVersion "1.0.0"
#define AppPublisher "chus.vn"

[Setup]
AppId={{B7D4F1A2-9C3E-4A55-8E21-DRIVEDL0001}}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
UninstallDisplayIcon={app}\Drive Downloader.exe
OutputDir=Output
OutputBaseFilename=DriveDownloader-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "vi"; MessagesFile: "compiler:Languages\Vietnamese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Bundle the entire PyInstaller onedir output.
Source: "dist\Drive Downloader\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\Drive Downloader.exe"
Name: "{commondesktop}\{#AppName}"; Filename: "{app}\Drive Downloader.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Drive Downloader.exe"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
