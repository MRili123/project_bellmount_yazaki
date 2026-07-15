; Inno Setup script — builds the single-file installer
; yazaki_bellmounth_mesure_setup.exe from the PyInstaller dist folder.
; Compile: ISCC.exe installer.iss

[Setup]
AppName=Yazaki Bellmounth Mesure
AppVersion=2.0
AppPublisher=Yazaki
; Per-user install (no admin needed) and the app can write config.json/.env
; next to its exe. The wizard still lets the user pick any folder.
DefaultDirName={localappdata}\YazakiBellmounthMesure
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
OutputDir=C:\BellmouthProject\app\dist
OutputBaseFilename=yazaki_bellmounth_mesure_setup
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
SetupIconFile=C:\BellmouthProject\app\app_icon.ico
UninstallDisplayIcon={app}\Bellmounth.exe

[Files]
Source: "C:\BellmouthProject\app\dist\Bellmounth\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{autodesktop}\Yazaki Bellmounth Mesure"; Filename: "{app}\Bellmounth.exe"; WorkingDir: "{app}"
Name: "{autoprograms}\Yazaki Bellmounth Mesure"; Filename: "{app}\Bellmounth.exe"; WorkingDir: "{app}"

[Run]
Filename: "{app}\Bellmounth.exe"; Description: "Launch Yazaki Bellmounth Mesure"; Flags: nowait postinstall skipifsilent
