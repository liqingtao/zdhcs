@echo off
setlocal
cd /d "%~dp0..\.."

if not exist "dist\zdhcs\zdhcs.exe" (
    echo [ERROR] 未找到 dist\zdhcs\zdhcs.exe，请先运行 build_windows.bat 完成打包。
    exit /b 1
)

set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
    set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"
)
if not exist "%ISCC%" (
    echo [ERROR] 未找到 Inno Setup，请先安装：https://jrsoftware.org/isinfo.php
    exit /b 1
)

"%ISCC%" "build\windows\installer.iss"

echo.
echo 安装包生成完成：dist\installer\zdhcs-setup.exe
pause

