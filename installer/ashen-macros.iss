; Ashen Macros first-install script (Inno Setup).
; Default: per-user %LOCALAPPDATA%\Ashen Macros
; Custom directories are allowed; Inno elevates when the chosen path requires it.
;
; Build with:
;   ISCC /DMyAppVersion=2026.32 installer\ashen-macros.iss
;
; Expects PyInstaller output at dist\launcher\

#ifndef MyAppVersion
  #error MyAppVersion must be defined (e.g. /DMyAppVersion=2026.32)
#endif

#define MyAppName "Ashen Macros"
#define MyAppPublisher "Ashen Macros"
#define MyAppExeName "launcher.exe"
#define MyAppURL "https://github.com/koetsmax/Ashen-Macros-2.0"

[Setup]
AppId={{A8E5C2F1-4B3D-4E9A-9C1F-7D2E6B8A5F01}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
DefaultDirName={localappdata}\Ashen Macros
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
AllowNoIcons=yes
; Prefer per-user installs; allow elevation when the user picks a protected path.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist
OutputBaseFilename=Ashen.Macro.installer
Compression=lzma
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Pack the PyInstaller COLLECT output (launcher.exe + _internal\...).
Source: "..\dist\launcher\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
