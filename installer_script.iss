#define MyAppName "SC Command"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Space Man Rob"
#define MyAppExeName "sc_command.exe"

[Setup]
AppId={{A4D03AE3-4CE9-4458-B7D8-2939F2D67A67}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=SCCommandSetup
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\sc_command.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Code]
var
  GameLogPathPage: TInputFileWizardPage;

procedure InitializeWizard;
begin
  GameLogPathPage := CreateInputFilePage(wpSelectDir,
    'Select Star Citizen Game.log', 'Where is your Star Citizen Game.log file located?',
    'Please select your Game.log file location, then click Next.');
    
  GameLogPathPage.Add('Game.log location:',
    'Log files (Game.log)|Game.log|All files (*.*)|*.*',
    '.log');
end;

procedure SaveGameLogPath(Path: String);
var
  AppDataDir: String;
  ConfigFile: String;
begin
  AppDataDir := ExpandConstant('{userappdata}\SCCommand');
  CreateDir(AppDataDir);
  ConfigFile := AppDataDir + '\game_log_path.txt';
  SaveStringToFile(ConfigFile, GameLogPathPage.Values[0], False);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = GameLogPathPage.ID then
  begin
    if not FileExists(GameLogPathPage.Values[0]) then
    begin
      MsgBox('Please select a valid Game.log file.', mbError, MB_OK);
      Result := False;
    end;
  end;
end;

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    SaveGameLogPath(ExpandConstant('{app}'));
end;