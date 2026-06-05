; TalkPC Pro Installer (Inno Setup 6.x)
; 鍮뚮뱶: ISCC TalkPC-Pro.iss ??output/TalkPC-Pro-Setup-v{version}.exe

#define MyAppName "TalkPC Pro"
#define MyAppNameKey "TalkPC-Pro"
#define MyAppVersion "0.1.11"
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

; ASCII-safe 寃쎈줈 媛뺤젣 (paddle_inference ?쒓? 寃쎈줈 遺덇?)
DefaultDirName={autopf}\{#MyAppNameKey}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
DisableDirPage=no
; ?쒓? ?ъ슜?먭? ?ㅼ튂 寃쎈줈 蹂寃??쒕룄 ???쒓? 寃쎈줈 李⑤떒
UsePreviousAppDir=yes

; 異쒕젰
OutputDir=output
; 踰꾩쟾 誘명룷??怨좎젙 ?뚯씪紐???landing ??吏곸젒 ?ㅼ슫濡쒕뱶 留곹겕??; (/releases/latest/download/TalkPC-Pro-Setup.exe 媛 ??긽 理쒖떊 媛由ы궡)
OutputBaseFilename=TalkPC-Pro-Setup
SetupIconFile=
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern

; 沅뚰븳 ??Program Files ?ㅼ튂??admin ?꾩슂
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible

; ?몄뼱
ShowLanguageDialog=no

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#SourceDir}\TalkPC-Pro.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs
; Microsoft Visual C++ 2015-2022 x64 ?щ같????PaddleOCR DLL ?고????섏〈??
; 誘몄꽕移?PC ?먯꽌 paddleocr import ?ㅽ뙣 ??諛쒖넚 臾댄븳?湲곕줈 吏곴껐?? ??긽 ?숇큺.
Source: "redist\VC_redist.x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; VC++ ?щ같????誘몄꽕移??쒖뿉留?silent ?ㅼ튂. ?대? 媛숆굅??理쒖떊?대㈃ redist ?먯껜媛 利됱떆 醫낅즺.
Filename: "{tmp}\VC_redist.x64.exe"; Parameters: "/install /quiet /norestart"; StatusMsg: "Microsoft Visual C++ ?고????ㅼ튂 以?.."; Check: VCRedistNeedsInstall
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
function VCRedistNeedsInstall: Boolean;
var
  Installed: Cardinal;
begin
  // VC++ 2015-2022 x64 ?고??꾩씠 ?뺤긽 ?ㅼ튂?섎㈃
  //   HKLM\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64\Installed = 1
  // ???먯껜媛 ?녾굅??0 ?대㈃ ?ㅼ튂 ?꾩슂.
  if RegQueryDWordValue(HKLM64,
       'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64',
       'Installed', Installed) then
    Result := (Installed = 0)
  else
    Result := True;
end;

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
        '?ㅼ튂 寃쎈줈???쒓????ы븿?섎㈃ OCR ?붿쭊???묐룞?섏? ?딆뒿?덈떎.' + #13#10 +
        '?곷Ц 寃쎈줈濡?蹂寃쏀빐二쇱꽭??' + #13#10 + #13#10 +
        '沅뚯옣 寃쎈줈: C:\Program Files\TalkPC-Pro\',
        mbError, MB_OK
      );
      Result := False;
    end;
  end;
end;

