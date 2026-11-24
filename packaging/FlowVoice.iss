; Inno Setup script for Flow Voice. Built by packaging\build.ps1 (needs dist\FlowVoice from PyInstaller).
;   ISCC.exe /DAppVersion=0.1.0 /DWithModel=1            -> FlowVoice-0.1.0-Setup.exe        (speech model inside, works offline)
;   ISCC.exe /DAppVersion=0.1.0 /DWithModel=0 /DSuffix=-Lite -> FlowVoice-0.1.0-Setup-Lite.exe (small; downloads the model once)
; Installs for the current user only: no administrator rights, nothing outside your profile.
; Settings and history live in %APPDATA%\FlowVoice and are never touched by install or uninstall.

#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif
#ifndef WithModel
  #define WithModel 1
#endif
#ifndef Suffix
  #define Suffix ""
#endif

[Setup]
AppId={{7AD21A73-31D2-447B-A52C-BF34296B1DEA}
AppName=Flow Voice
AppVersion={#AppVersion}
AppVerName=Flow Voice {#AppVersion}
AppPublisher=Flow Voice
AppPublisherURL=https://github.com/camh1473/Flow-Voice
AppSupportURL=https://github.com/camh1473/Flow-Voice/issues
DefaultDirName={localappdata}\Programs\FlowVoice
DefaultGroupName=Flow Voice
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=FlowVoice-{#AppVersion}-Setup{#Suffix}
SetupIconFile=..\src\flowvoice\assets\flowvoice.ico
UninstallDisplayIcon={app}\FlowVoice.exe
UninstallDisplayName=Flow Voice
Compression=lzma2/normal
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
VersionInfoVersion={#AppVersion}
VersionInfoDescription=Flow Voice setup
CloseApplications=no

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; Flags: unchecked

[Files]
#if WithModel
Source: "..\dist\FlowVoice\*"; DestDir: "{app}"; Excludes: "Install-FlowVoice.*"; Flags: recursesubdirs createallsubdirs ignoreversion
#else
Source: "..\dist\FlowVoice\*"; DestDir: "{app}"; Excludes: "models\*,Install-FlowVoice.*"; Flags: recursesubdirs createallsubdirs ignoreversion
#endif

[Icons]
Name: "{autoprograms}\Flow Voice"; Filename: "{app}\FlowVoice.exe"
Name: "{autodesktop}\Flow Voice"; Filename: "{app}\FlowVoice.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\FlowVoice.exe"; Description: "Start Flow Voice"; Flags: nowait postinstall skipifsilent

[Code]
const
  RunKey = 'Software\Microsoft\Windows\CurrentVersion\Run';

procedure StopFlowVoice;
var
  Code: Integer;
begin
  { Only the packaged FlowVoice.exe is touched; a copy run from source (pythonw.exe) is left alone. }
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM FlowVoice.exe', '', SW_HIDE, ewWaitUntilTerminated, Code);
  Sleep(800);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  StopFlowVoice;
  Result := '';
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Value: String;
begin
  if CurUninstallStep = usUninstall then
  begin
    StopFlowVoice;
    { The app itself writes the start-with-Windows entry; remove it only if it points at this install. }
    if RegQueryStringValue(HKCU, RunKey, 'FlowVoice', Value) then
      if Pos(Lowercase(ExpandConstant('{app}')), Lowercase(Value)) > 0 then
        RegDeleteValue(HKCU, RunKey, 'FlowVoice');
  end;
end;
