@echo off
setlocal
cd /d "%~dp0..\.."

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] 未找到 python。请先安装 Python 3.9+，并勾选 "Add python.exe to PATH"。
    exit /b 1
)

if not exist ".venv-win" (
    python -m venv .venv-win
)
call ".venv-win\Scripts\activate.bat"

python -m pip install --upgrade pip
python -m pip install "numpy<2" opencv-python-headless==4.9.0.80 Pillow PyAutoGUI pyinstaller

pyinstaller --clean --noconfirm zdhcs.spec

echo.
echo 打包完成：dist\zdhcs\zdhcs.exe
echo 可执行文件目录：dist\zdhcs\
echo 如需生成 Setup.exe 安装包，请安装 Inno Setup 后运行 build\windows\build_installer.bat
pause

