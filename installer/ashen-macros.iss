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
  OurUninstallKey = '{A8E5C2F1-4B3D-4E9A-9C1F-7D2E6B8A5F01}_is1';

function IsOurInnoKey(const SubKey: String): Boolean;
begin
  Result := SameText(SubKey, OurUninstallKey);
end;

function IsLegacyAshen(const SubKey, DisplayName: String): Boolean;
var
  LowerName: String;
begin
  if IsOurInnoKey(SubKey) then
  begin
    Result := False;
    Exit;
  end;

  { Known InstallForge product key / name }
  if SameText(SubKey, 'Ashen Macro''s 2.0') then
  begin
    Result := True;
    Exit;
  end;

  LowerName := LowerCase(DisplayName);
  if Pos('ashen macro', LowerName) = 0 then
  begin
    Result := False;
    Exit;
  end;

  { New Inno display names look like "Ashen Macros 2026.32" — skip those. }
  if Pos('ashen macros 20', LowerName) = 1 then
  begin
    Result := False;
    Exit;
  end;

  Result :=
    (Pos('ashen macro''s', LowerName) > 0) or
    (Pos('2.0', DisplayName) > 0) or
    (Pos('ashen alliance', LowerName) > 0);
end;

function FindLegacyUninstall(var UninstallCmd, DisplayName: String): Boolean;
var
  Roots: array[0..2] of Integer;
  RootIdx, I: Integer;
  SubKeys: TArrayOfString;
  SubKey, Name, Cmd: String;
begin
  Result := False;
  UninstallCmd := '';
  DisplayName := '';

  Roots[0] := HKLM32;
  Roots[1] := HKLM64;
  Roots[2] := HKCU;

  for RootIdx := 0 to GetArrayLength(Roots) - 1 do
  begin
    if not RegGetSubkeyNames(Roots[RootIdx], 'Software\Microsoft\Windows\CurrentVersion\Uninstall', SubKeys) then
      Continue;

    for I := 0 to GetArrayLength(SubKeys) - 1 do
    begin
      SubKey := SubKeys[I];
      if not RegQueryStringValue(
        Roots[RootIdx],
        'Software\Microsoft\Windows\CurrentVersion\Uninstall\' + SubKey,
        'DisplayName',
        Name
      ) then
        Continue;

      if not IsLegacyAshen(SubKey, Name) then
        Continue;

      if not RegQueryStringValue(
        Roots[RootIdx],
        'Software\Microsoft\Windows\CurrentVersion\Uninstall\' + SubKey,
        'UninstallString',
        Cmd
      ) then
        Continue;

      if Trim(Cmd) = '' then
        Continue;

      UninstallCmd := Trim(Cmd);
      DisplayName := Name;
      Result := True;
      Exit;
    end;
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

procedure RunLegacyUninstaller(const Cmd: String);
var
  Path, Params: String;
  ResultCode: Integer;
begin
  SplitCommand(Cmd, Path, Params);
  if (Path = '') or not FileExists(Path) then
  begin
    MsgBox(
      'Could not find the old Ashen Macros uninstaller. You can remove it later from Windows Settings.',
      mbError,
      MB_OK
    );
    Exit;
  end;

  { Old install lives under Program Files — request elevation. }
  if ShellExec('runas', Path, Params, '', SW_SHOW, ewWaitUntilTerminated, ResultCode) then
  begin
    if ResultCode <> 0 then
      MsgBox(
        'The old uninstall finished with exit code ' + IntToStr(ResultCode) +
        '. Continuing with the new install.',
        mbInformation,
        MB_OK
      );
    Exit;
  end;

  if Exec(Path, Params, '', SW_SHOW, ewWaitUntilTerminated, ResultCode) then
  begin
    if ResultCode <> 0 then
      MsgBox(
        'The old uninstall finished with exit code ' + IntToStr(ResultCode) +
        '. Continuing with the new install.',
        mbInformation,
        MB_OK
      );
    Exit;
  end;

  MsgBox(
    'Failed to start the old uninstaller. You can remove it later from Windows Settings. Continuing with the new install.',
    mbError,
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
