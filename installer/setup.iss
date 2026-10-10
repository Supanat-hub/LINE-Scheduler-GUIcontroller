; =====================================================================
; Inno Setup Script for LINE Scheduler (GUI Automation)
; =====================================================================

#define MyAppName "LINE Scheduler"
#define MyAppVersion "1.0.3"
#define MyAppPublisher "LINE Scheduler"
#define MyAppExeName "LineScheduler.exe"

[Setup]
; App Metadata
AppId={{5C88F219-9B21-4E65-B8FA-7F4DC81D923E}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\LineScheduler
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=..\dist\installer
OutputBaseFilename=LineScheduler-Setup
SetupIconFile=..\assets\icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "startupicon"; Description: "เปิดโปรแกรมพร้อมเปิดเครื่อง Windows (Auto-start on Login)"; GroupDescription: "{cm:AdditionalIcons}"
Name: "defenderexclusion"; Description: "เพิ่มในข้อยกเว้น Windows Defender (ป้องกันการลบไฟล์ผิดพลาด)"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; รวบรวมไฟล์ทั้งหมดจากโฟลเดอร์ dist\LineScheduler ที่ PyInstaller สร้างขึ้น
Source: "..\dist\LineScheduler\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; ลบ Shortcut เก่าใน Startup folder ป้องกันการเปิดโปรแกรมซ้ำซ้อน 2 หน้าต่าง
Type: files; Name: "{userstartup}\{#MyAppName}.lnk"

[Icons]
Name: "{autoprograms}\{#MyAppName}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autoprograms}\{#MyAppName}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; จัดการ Auto-start ผ่าน Registry เพียงช่องทางเดียว ป้องกันปัญหาเปิดซ้อนกับ Startup folder
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "LineScheduler"; ValueData: """{app}\{#MyAppExeName}"""; Flags: uninsdeletevalue; Tasks: startupicon

[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -WindowStyle Hidden -Command ""Add-MpPreference -ExclusionPath '{app}' -ExclusionProcess '{#MyAppExeName}'"""; Verb: runas; Tasks: defenderexclusion; Flags: runhidden shellexec
Filename: "{app}\{#MyAppExeName}"; Description: "เปิดใช้งาน {#MyAppName} ทันที"; Flags: nowait postinstall skipifsilent

