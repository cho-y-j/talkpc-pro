; TalkPC Pro Installer (Inno Setup 6.x)
; 빌드: ISCC TalkPC-Pro.iss → output/TalkPC-Pro-Setup-v{version}.exe

#define MyAppName "TalkPC Pro"
#define MyAppNameKey "TalkPC-Pro"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "TalkPC Pro"
#define MyAppURL "https://talkpc-pro-yf6w.vercel.app"
#define MyAppExeName "TalkPC-Pro.exe"
#define SourceDir "..\client\dist\TalkPC-Pro"

[Setup]
AppId={{B7E1F5C2-9A3D-4F1E-8C7B-1D4E2F5A8B9C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}/download

; ASCII-safe 경로 강제 (paddle_inference 한글 경로 불가)
DefaultDirName={autopf}\{#MyAppNameKey}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
DisableDirPage=no
; 한글 사용자가 설치 경로 변경 시도 시 한글 경로 차단
UsePreviousAppDir=yes

; 출력
OutputDir=output
; 버전 미포함 고정 파일명 — landing 의 직접 다운로드 링크용
; (/releases/latest/download/TalkPC-Pro-Setup.exe 가 항상 최신 가리킴)
OutputBaseFilename=TalkPC-Pro-Setup
SetupIconFile=
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern

; 권한 — Program Files 설치라 admin 필요
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible

; 언어
ShowLanguageDialog=no

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#SourceDir}\TalkPC-Pro.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
function IsAsciiPath(const Path: string): Boolean;
var
  i: Integer;
begin
  Result := True;
  for i := 1 to Length(Path) do
  begin
    if Ord(Path[i]) > 127 then
    begin
      Result := False;
      Exit;
    end;
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = wpSelectDir then
  begin
    if not IsAsciiPath(WizardForm.DirEdit.Text) then
    begin
      MsgBox(
        '설치 경로에 한글이 포함되면 OCR 엔진이 작동하지 않습니다.' + #13#10 +
        '영문 경로로 변경해주세요.' + #13#10 + #13#10 +
        '권장 경로: C:\Program Files\TalkPC-Pro\',
        mbError, MB_OK
      );
      Result := False;
    end;
  end;
end;
