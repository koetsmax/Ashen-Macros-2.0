; Ashen Macros first-install script (Inno Setup).
; Default: per-user %LOCALAPPDATA%\Ashen Macros
;
; Build with:
;   ISCC /DMyAppVersion=2026.32 installer\ashen-macros.iss
;
; Expects PyInstaller output at dist\Ashen Macros\

#ifndef MyAppVersion
  #error MyAppVersion must be defined (e.g. /DMyAppVersion=2026.32)
#endif

#define MyAppName "Ashen Macros"
#define MyAppPublisher "Ashen Macros"
#define MyAppExeName "Ashen Macros.exe"
#define MyAppURL "https://github.com/koetsmax/Ashen-Macros-2.0"
#define MyAppIcon "..\images\AshenAllianceLogo.ico"
#define MyAppId "{{A8E5C2F1-4B3D-4E9A-9C1F-7D2E6B8A5F01}"

[Setup]
AppId={#MyAppId}
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
; Per-user only (no all-users / elevation choice).
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=Ashen.Macro.installer
Compression=lzma
SolidCompression=yes
WizardStyle=modern
SetupIconFile={#MyAppIcon}
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Pack the PyInstaller COLLECT output (Ashen Macros.exe + _internal\...).
Source: "..\dist\Ashen Macros\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
const
  LegacyUninstallSubkey =
    'Software\Microsoft\Windows\CurrentVersion\Uninstall\Ashen Macro''s 2.0';

function FindLegacyUninstall(var UninstallCmd, DisplayName: String): Boolean;
var
  Roots: array[0..2] of Integer;
  RootIdx: Integer;
  Name, Cmd: String;
begin
  Result := False;
  UninstallCmd := '';
  DisplayName := '';

  Roots[0] := HKLM32;
  Roots[1] := HKLM64;
  Roots[2] := HKCU;

  for RootIdx := 0 to GetArrayLength(Roots) - 1 do
  begin
    if not RegQueryStringValue(Roots[RootIdx], LegacyUninstallSubkey, 'UninstallString', Cmd) then
      Continue;
    if Trim(Cmd) = '' then
      Continue;

    UninstallCmd := Trim(Cmd);
    if not RegQueryStringValue(Roots[RootIdx], LegacyUninstallSubkey, 'DisplayName', Name) then
      Name := 'Ashen Macro''s 2.0';
    DisplayName := Name;
    Result := True;
    Exit;
  end;
end;

procedure SplitCommand(const Cmd: String; var Path, Params: String);
var
  S: String;
  P: Integer;
begin
  S := Trim(Cmd);
  Path := S;
  Params := '';

  if (Length(S) >= 2) and (S[1] = '"') then
  begin
    Delete(S, 1, 1);
    P := Pos('"', S);
    if P > 0 then
    begin
      Path := Copy(S, 1, P - 1);
      Params := Trim(Copy(S, P + 1, MaxInt));
    end
    else
      Path := S;
  end;
end;

{ InstallForge stores UninstallString without a .exe suffix. }
function ResolveUninstallExe(const Path: String): String;
var
  Candidate: String;
begin
  Result := Path;
  if (Path <> '') and FileExists(Path) then
    Exit;

  if Path <> '' then
  begin
    Candidate := Path + '.exe';
    if FileExists(Candidate) then
    begin
      Result := Candidate;
      Exit;
    end;
  end;

  if Path <> '' then
  begin
    Candidate := AddBackslash(ExtractFilePath(Path)) + 'Uninstall.exe';
    if FileExists(Candidate) then
    begin
      Result := Candidate;
      Exit;
    end;
  end;

  Result := '';
end;

procedure RunLegacyUninstaller(const Cmd: String);
var
  Path, Params: String;
  ResultCode: Integer;
  Started: Boolean;
begin
  SplitCommand(Cmd, Path, Params);
  Path := ResolveUninstallExe(Path);
  if Path = '' then
  begin
    MsgBox(
      'Could not find the old Ashen Macros uninstaller. You can remove it later from Windows Settings.',
      mbError,
      MB_OK
    );
    Exit;
  end;

  { Old install is under Program Files — request elevation, then fall back. }
  Started := ShellExec('runas', Path, Params, '', SW_SHOW, ewWaitUntilTerminated, ResultCode);
  if not Started then
    Started := Exec(Path, Params, '', SW_SHOW, ewWaitUntilTerminated, ResultCode);

  if not Started then
  begin
    MsgBox(
      'Failed to start the old uninstaller. You can remove it later from Windows Settings. Continuing with the new install.',
      mbError,
      MB_OK
    );
    Exit;
  end;

  if ResultCode <> 0 then
    MsgBox(
      'The old uninstall finished with exit code ' + IntToStr(ResultCode) +
      '. Continuing with the new install.',
      mbInformation,
      MB_OK
    );
end;

function InitializeSetup(): Boolean;
var
  UninstallCmd, DisplayName: String;
begin
  Result := True;

  if WizardSilent then
    Exit;

  if not FindLegacyUninstall(UninstallCmd, DisplayName) then
    Exit;

  if MsgBox(
    'An older version was found:' + #13#10 + DisplayName + #13#10#13#10 +
    'Uninstall it before installing the new Ashen Macros?' + #13#10#13#10 +
    'Choose No to keep both installs.',
    mbConfirmation,
    MB_YESNO
  ) = IDYES then
    RunLegacyUninstaller(UninstallCmd);
end;
