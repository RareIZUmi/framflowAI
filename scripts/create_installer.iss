; FrameFlow AI — Inno Setup Installer Script
; Generates a Windows installer for FrameFlow AI
; Requires: Inno Setup 6+ (https://jrsoftware.org/isinfo.php)
;
; Usage: Open this file in Inno Setup Compiler and click Build.
; Prerequisite: Run `python scripts/build.py` first to create dist/FrameFlowAI/

#define AppName "FrameFlow AI"
#define AppVersion "1.0.0"
#define AppPublisher "FrameFlow AI Team"
#define AppURL "https://frameflow.ai"
#define AppExeName "FrameFlowAI.exe"

[Setup]
AppId={{B8E7F3A2-4D1C-4A89-9E5D-2F3B8C6D7E9A}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
OutputDir=..\installer
OutputBaseFilename=FrameFlowAI-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
; Uncomment and set path when icon is available:
; SetupIconFile=..\src\resources\icons\app.ico
WizardStyle=modern
WizardSizePercent=120

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Bundle the entire PyInstaller output directory
Source: "..\dist\FrameFlowAI\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Registry]
; Register file associations for video files
Root: HKCU; Subkey: "Software\Classes\.mp4\OpenWithProgids"; ValueType: string; ValueName: "FrameFlowAI.Video"; ValueData: ""; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\.mkv\OpenWithProgids"; ValueType: string; ValueName: "FrameFlowAI.Video"; ValueData: ""; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\.mov\OpenWithProgids"; ValueType: string; ValueName: "FrameFlowAI.Video"; ValueData: ""; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\.avi\OpenWithProgids"; ValueType: string; ValueName: "FrameFlowAI.Video"; ValueData: ""; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\.webm\OpenWithProgids"; ValueType: string; ValueName: "FrameFlowAI.Video"; ValueData: ""; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\FrameFlowAI.Video"; ValueType: string; ValueName: ""; ValueData: "FrameFlow AI Video"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\FrameFlowAI.Video\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" ""%1"""
