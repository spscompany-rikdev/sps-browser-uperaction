; ═══════════════════════════════════════════════════════════════════════════
;  SPS_Browser_Setup.iss  -  Inno Setup 6 installer script for SPS Browser
;
;  Creates:  installer\Output\SPS_Browser_Setup_v<version>.exe
;
;  HOW TO USE
;    1. Run BUILD.bat first (creates dist\SPS_Browser\ and downloads installer\redist\vc_redist.x64.exe)
;    2. Open this file in Inno Setup Compiler and press F9 (BUILD.bat does it for you when Inno Setup is installed)
;
;  IMPORTANT - the AppId below is the permanent identity of SPS Browser. EVERY installer of EVERY version must use
;  exactly this value, because Windows (Apps & features), upgrades and the updater all recognise the product by it.
;  Windows stores it as   ...\Uninstall\{1F897549-179B-4C8C-9B8B-EC93AC62EAB3}_is1
;
;  What the setup does
;    - asks for administrator permission ONCE (needed for Program Files and the Visual C++ runtime)
;    - if an older SPS Browser is installed it is UNINSTALLED FIRST - your profiles, bookmarks and settings are kept
;      (an upgrade runs the old uninstaller with /KEEPDATA; only a manual uninstall deletes everything)
;    - installs SPS Browser (sandbox + browser + AI libraries) and, when needed, the Visual C++ runtime silently
;    - creates Start Menu / Desktop shortcuts and the uninstaller
;    - supports silent use by the built-in updater:   Setup.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /RELAUNCH
; ═══════════════════════════════════════════════════════════════════════════

#define APP_NAME        "SPS Browser"
#define APP_VERSION     "36.0.0"
#define APP_PUBLISHER   "SPS Software"
#define APP_URL         "https://sites.google.com/view/spsbrowserpro"
#define APP_EXE         "SPS_Browser.exe"
#define APP_ID          "{1F897549-179B-4C8C-9B8B-EC93AC62EAB3}"
#define DIST_FOLDER     "..\dist\SPS_Browser"
#define VCREDIST        "redist\vc_redist.x64.exe"

[Setup]
; '{{' is Inno's escape for a literal '{'
AppId={{1F897549-179B-4C8C-9B8B-EC93AC62EAB3}
AppName={#APP_NAME}
AppVersion={#APP_VERSION}
AppVerName={#APP_NAME} {#APP_VERSION}
AppPublisher={#APP_PUBLISHER}
AppPublisherURL={#APP_URL}
AppSupportURL={#APP_URL}
AppUpdatesURL={#APP_URL}/updates
VersionInfoVersion={#APP_VERSION}.0
VersionInfoProductName={#APP_NAME}
VersionInfoCompany={#APP_PUBLISHER}
VersionInfoDescription={#APP_NAME} Setup

DefaultDirName={autopf}\{#APP_NAME}
DefaultGroupName={#APP_NAME}
DisableProgramGroupPage=yes
AllowNoIcons=yes

OutputDir=Output
OutputBaseFilename=SPS_Browser_Setup_v{#APP_VERSION}
Compression=lzma2/max
SolidCompression=yes
SetupLogging=yes

WizardStyle=modern
SetupIconFile=..\assets\sps_browser.ico

; licence page (GPL-3.0) is shown during setup
LicenseFile=license_installer.txt

; one UAC prompt at the start -> the VC++ runtime can then be installed completely silently
PrivilegesRequired=admin
MinVersion=10.0
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; running SPS Browser windows are closed automatically (also in silent mode); the updater relaunches it afterwards
CloseApplications=yes
RestartApplications=no

UninstallDisplayName={#APP_NAME}
UninstallDisplayIcon={app}\{#APP_EXE}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &Desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
; Everything PyInstaller built: SPS_Browser.exe, SPS_Browser_Core.exe, _internal\ (Python, Qt, llama.cpp), assets\, local_ai\ ...
Source: "{#DIST_FOLDER}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; Licence texts (always installed, also readable inside the browser: More Features > License & Legal)
Source: "..\LICENSE.txt";                     DestDir: "{app}"; Flags: ignoreversion
Source: "..\extras\SPS_BROWSER_NOTICE.txt";   DestDir: "{app}"; Flags: ignoreversion
Source: "..\extras\THIRD_PARTY_NOTICES.txt";  DestDir: "{app}"; Flags: ignoreversion

; Microsoft Visual C++ runtime - copied to a temp folder only when it is really needed
#ifexist SourcePath + VCREDIST
Source: "{#VCREDIST}"; DestDir: "{tmp}"; Flags: deleteafterinstall; Check: VCRedistNeeded
#else
#pragma warning "installer\redist\vc_redist.x64.exe is missing - this installer will NOT install the Visual C++ runtime. Run BUILD.bat to download it."
#endif

[Icons]
Name: "{group}\{#APP_NAME}"; Filename: "{app}\{#APP_EXE}"; WorkingDir: "{app}"
Name: "{group}\License"; Filename: "{app}\LICENSE.txt"
Name: "{group}\Uninstall {#APP_NAME}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#APP_NAME}"; Filename: "{app}\{#APP_EXE}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
; 1) Visual C++ runtime: completely silent, no window, no restart. Skipped when already installed.
#ifexist SourcePath + VCREDIST
Filename: "{tmp}\vc_redist.x64.exe"; Parameters: "/install /quiet /norestart"; StatusMsg: "Installing Microsoft Visual C++ runtime..."; Flags: waituntilterminated runhidden; Check: VCRedistNeeded
#endif
; 2) normal setup: offer to launch SPS Browser (always through the sandbox exe)
Filename: "{app}\{#APP_EXE}"; Description: "Launch {#APP_NAME} now"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent
; 3) update started by the browser itself (/RELAUNCH): start the new version again, as the normal (non-admin) user
Filename: "{app}\{#APP_EXE}"; WorkingDir: "{app}"; Flags: nowait runasoriginaluser; Check: RelaunchRequested

[Registry]
Root: HKA; Subkey: "Software\{#APP_PUBLISHER}\{#APP_NAME}"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\{#APP_PUBLISHER}\{#APP_NAME}"; ValueType: string; ValueName: "Version"; ValueData: "{#APP_VERSION}"

; Makes SPS Browser appear in Windows Settings > Default apps (the user still confirms the choice there - Windows requires it)
Root: HKLM; Subkey: "Software\Clients\StartMenuInternet\SPS Browser"; ValueType: string; ValueData: "SPS Browser"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\Clients\StartMenuInternet\SPS Browser\Capabilities"; ValueType: string; ValueName: "ApplicationName"; ValueData: "SPS Browser"
Root: HKLM; Subkey: "Software\Clients\StartMenuInternet\SPS Browser\Capabilities"; ValueType: string; ValueName: "ApplicationDescription"; ValueData: "Fast, private, secure web browser"
Root: HKLM; Subkey: "Software\Clients\StartMenuInternet\SPS Browser\Capabilities\URLAssociations"; ValueType: string; ValueName: "http"; ValueData: "SPSBrowser.URL"
Root: HKLM; Subkey: "Software\Clients\StartMenuInternet\SPS Browser\Capabilities\URLAssociations"; ValueType: string; ValueName: "https"; ValueData: "SPSBrowser.URL"
Root: HKLM; Subkey: "Software\Clients\StartMenuInternet\SPS Browser\Capabilities\FileAssociations"; ValueType: string; ValueName: ".html"; ValueData: "SPSBrowser.HTML"
Root: HKLM; Subkey: "Software\Clients\StartMenuInternet\SPS Browser\Capabilities\FileAssociations"; ValueType: string; ValueName: ".htm"; ValueData: "SPSBrowser.HTML"
Root: HKLM; Subkey: "Software\Clients\StartMenuInternet\SPS Browser\shell\open\command"; ValueType: string; ValueData: """{app}\{#APP_EXE}"""
Root: HKLM; Subkey: "Software\RegisteredApplications"; ValueType: string; ValueName: "SPS Browser"; ValueData: "Software\Clients\StartMenuInternet\SPS Browser\Capabilities"; Flags: uninsdeletevalue
Root: HKLM; Subkey: "Software\Classes\SPSBrowser.URL"; ValueType: string; ValueData: "SPS Browser URL"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\Classes\SPSBrowser.URL"; ValueType: string; ValueName: "URL Protocol"; ValueData: ""
Root: HKLM; Subkey: "Software\Classes\SPSBrowser.URL\shell\open\command"; ValueType: string; ValueData: """{app}\{#APP_EXE}"" ""%1"""
Root: HKLM; Subkey: "Software\Classes\SPSBrowser.HTML"; ValueType: string; ValueData: "SPS Browser HTML Document"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\Classes\SPSBrowser.HTML\shell\open\command"; ValueType: string; ValueData: """{app}\{#APP_EXE}"" ""%1"""

[UninstallRun]
; stop every SPS process first, otherwise Windows keeps the files locked and they cannot be deleted.
; (No /T: the Job Object already ends the helper processes, and /T could also end the setup that started the uninstall.)
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM SPS_Browser.exe";      Flags: runhidden skipifdoesntexist; RunOnceId: "KillSandbox"
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM SPS_Browser_Core.exe"; Flags: runhidden skipifdoesntexist; RunOnceId: "KillCore"

[UninstallDelete]
; the program folder is always removed
Type: filesandordirs; Name: "{app}"
; EVERYTHING SPS Browser created for the user is removed on a real uninstall - but NOT during an upgrade (/KEEPDATA)
Type: filesandordirs; Name: "{sd}\SPS_Browser";                Check: DeleteUserData
Type: filesandordirs; Name: "{localappdata}\SPS_Browser";      Check: DeleteUserData
Type: filesandordirs; Name: "{localappdata}\SPS";              Check: DeleteUserData
Type: filesandordirs; Name: "{userappdata}\SPS_Browser";       Check: DeleteUserData
Type: filesandordirs; Name: "{%USERPROFILE}\.sps_sandbox";     Check: DeleteUserData
Type: filesandordirs; Name: "{%USERPROFILE}\.sps_browser";     Check: DeleteUserData
Type: filesandordirs; Name: "{%USERPROFILE}\SPS_Browser";      Check: DeleteUserData
Type: files;          Name: "{%TEMP}\SPS_Sandbox_error.txt"
Type: files;          Name: "{%TEMP}\SPS_Browser_error.txt"
Type: files;          Name: "{%TEMP}\sps_newtab_*.html"
Type: files;          Name: "{%TEMP}\sps_lens_*.html"

[Code]
const
  // Where Windows records an Inno Setup installation:  ...\Uninstall\<AppId>_is1   (same AppId in every version)
  UNINSTALL_KEY = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#APP_ID}_is1';

// ---------------------------------------------------------------- command line helpers
function CmdLineHas(const Param: String): Boolean;
var
  I: Integer;
begin
  Result := False;
  for I := 1 to ParamCount do
    if CompareText(ParamStr(I), Param) = 0 then
    begin
      Result := True;
      Exit;
    end;
end;

function RelaunchRequested(): Boolean;
begin
  Result := CmdLineHas('/RELAUNCH');
end;

// True during an UPGRADE: the new setup runs the old uninstaller with /KEEPDATA so nothing of the user's is deleted.
function DeleteUserData(): Boolean;
begin
  Result := not CmdLineHas('/KEEPDATA');
end;

// ---------------------------------------------------------------- Visual C++ runtime
// True when the Visual C++ 2015-2022 x64 runtime is missing OR older than 14.38 (llama.cpp / Qt need a recent one).
// Setup runs in 64-bit mode, so HKLM below is the 64-bit registry view.
function VCRedistNeeded(): Boolean;
var
  Installed, Major, Minor: Cardinal;
  Key: String;
begin
  Result := True;
  Key := 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64';
  if RegQueryDWordValue(HKLM, Key, 'Installed', Installed) and (Installed = 1) then
    if RegQueryDWordValue(HKLM, Key, 'Major', Major) and RegQueryDWordValue(HKLM, Key, 'Minor', Minor) then
      Result := not ((Major = 14) and (Minor >= 38));
end;

// ---------------------------------------------------------------- uninstall the previous version FIRST
function FindOldUninstaller(var Path: String): Boolean;
var
  S: String;
begin
  Result := False;
  S := '';
  if RegQueryStringValue(HKLM, UNINSTALL_KEY, 'UninstallString', S)
     or RegQueryStringValue(HKCU, UNINSTALL_KEY, 'UninstallString', S) then
  begin
    Path := RemoveQuotes(S);
    Result := (Path <> '') and FileExists(Path);
  end;
end;

function OldVersionRegistered(): Boolean;
begin
  Result := RegKeyExists(HKLM, UNINSTALL_KEY) or RegKeyExists(HKCU, UNINSTALL_KEY);
end;

// Inno's uninstaller copies itself to a temp folder and the process we start ends early, so after Exec we wait
// until Windows no longer lists the old version (max. 90 s).
procedure UninstallOldVersion();
var
  Old: String;
  Code, Waited: Integer;
begin
  if not FindOldUninstaller(Old) then
    Exit;
  Log('Found an older SPS Browser, uninstalling it first (user data is kept): ' + Old);
  if Exec(Old, '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /KEEPDATA', '', SW_HIDE, ewWaitUntilTerminated, Code) then
  begin
    Waited := 0;
    while OldVersionRegistered() and (Waited < 90000) do
    begin
      Sleep(500);
      Waited := Waited + 500;
    end;
    Log('Old version removed after ' + IntToStr(Waited) + ' ms');
  end
  else
    Log('Could not start the old uninstaller (code ' + IntToStr(Code) + ') - continuing with an in-place upgrade');
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  UninstallOldVersion();
  Result := '';
end;

// ---------------------------------------------------------------- uninstall: remove what Inno does not know about
procedure DeleteForAllUsers(const SubPath: String);
var
  FR: TFindRec;
  Base: String;
begin
  Base := ExpandConstant('{sd}\Users\');
  if FindFirst(Base + '*', FR) then
  try
    repeat
      if ((FR.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0) and (FR.Name <> '.') and (FR.Name <> '..') then
        DelTree(Base + FR.Name + '\' + SubPath, True, True, True);
    until not FindNext(FR);
  finally
    FindClose(FR);
  end;
end;

procedure CleanUserRegistry();
var
  Exts: TArrayOfString;
  I: Integer;
begin
  RegDeleteKeyIncludingSubkeys(HKCU, 'Software\Classes\SPSBrowser.HTML');
  RegDeleteKeyIncludingSubkeys(HKCU, 'Software\Classes\SPSBrowser.URL');
  RegDeleteKeyIncludingSubkeys(HKCU, 'Software\Classes\SPSBrowser.Document');
  RegDeleteKeyIncludingSubkeys(HKCU, 'Software\SPS Browser');
  RegDeleteKeyIncludingSubkeys(HKCU, 'Software\SPS Software');
  RegDeleteValue(HKCU, 'Software\RegisteredApplications', 'SPS Browser');
  RegDeleteValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Run', 'SPS Browser');
  SetArrayLength(Exts, 22);
  Exts[0] := '.html'; Exts[1] := '.htm'; Exts[2] := '.xhtml'; Exts[3] := '.png'; Exts[4] := '.jpg'; Exts[5] := '.jpeg';
  Exts[6] := '.gif'; Exts[7] := '.webp'; Exts[8] := '.bmp'; Exts[9] := '.svg'; Exts[10] := '.mp4'; Exts[11] := '.webm';
  Exts[12] := '.mp3'; Exts[13] := '.wav'; Exts[14] := '.ogg'; Exts[15] := '.pdf'; Exts[16] := '.txt'; Exts[17] := '.md';
  Exts[18] := '.json'; Exts[19] := '.xml'; Exts[20] := '.csv'; Exts[21] := '.py';
  for I := 0 to GetArrayLength(Exts) - 1 do
    RegDeleteValue(HKCU, 'Software\Classes\' + Exts[I] + '\OpenWithProgids', 'SPSBrowser.Document');
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    if DeleteUserData() then
    begin
      DelTree(ExpandConstant('{sd}\SPS_Browser'), True, True, True);   // profiles / history / passwords of every Windows account
      DeleteForAllUsers('.sps_sandbox');
      DeleteForAllUsers('.sps_browser');
      DeleteForAllUsers('AppData\Local\SPS_Browser');
      DeleteForAllUsers('AppData\Local\SPS');
      CleanUserRegistry();
    end;
    DelTree(ExpandConstant('{app}'), True, True, True);
  end;
end;
