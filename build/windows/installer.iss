; Inno Setup 安装脚本：把 dist\zdhcs\ 打成单文件 Setup.exe
[Setup]
AppName=zdhcs
AppVersion=0.1.1
DefaultDirName={autopf}\zdhcs
DefaultGroupName=zdhcs
OutputDir=..\..\dist\installer
OutputBaseFilename=zdhcs-setup
Compression=lzma
SolidCompression=yes
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest

[Files]
Source: "..\..\dist\zdhcs\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\zdhcs"; Filename: "{app}\zdhcs.exe"
Name: "{group}\卸载 zdhcs"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\zdhcs.exe"; Parameters: "selftest"; Flags: postinstall nowait skipifsilent

