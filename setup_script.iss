; Inno Setup Script for CampusNetLogin
#define MyAppName "校园网自动登录与状态栏守护"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "WUST CampusNet Helper"
#define MyAppExeName "CampusNetLogin.exe"

[Setup]
AppId={{E68A8694-8149-4A73-BA9D-33A41088719F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={userappdata}\Programs\CampusNetLogin
DisableProgramGroupPage=yes
OutputDir=release
OutputBaseFilename=CampusNetLogin-v{#MyAppVersion}-InnoSetup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "快捷方式:"
Name: "autostart"; Description: "开机自启动并常驻右下角状态栏托盘"; GroupDescription: "自启设置:"

[Files]
Source: "CampusNetLogin.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "Start_CampusNet.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "Daemon_CampusNet.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "config.json"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "CampusNetAutoLogin"; ValueData: """{app}\{#MyAppExeName}"" --tray"; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "立即运行校园网自动登录程序"; Flags: nowait postinstall skipifsilent
