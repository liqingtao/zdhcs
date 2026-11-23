$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..\..")

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "未找到 python。请先安装 Python 3.9+ 并加入 PATH。"
    exit 1
}

if (-not (Test-Path ".venv-win")) {
    python -m venv .venv-win
}

& ".venv-win\Scripts\python.exe" -m pip install --upgrade pip
& ".venv-win\Scripts\python.exe" -m pip install "numpy<2" Pillow PyAutoGUI pyinstaller
& ".venv-win\Scripts\python.exe" -m pip install "opencv-contrib-python==4.6.0.66"
& ".venv-win\Scripts\python.exe" -m pip install airtest pocoui
& ".venv-win\Scripts\python.exe" -m pip install --no-deps rapidocr_onnxruntime==1.4.4
& ".venv-win\Scripts\python.exe" -m pip install onnxruntime pyclipper shapely PyYAML tqdm six

& ".venv-win\Scripts\pyinstaller.exe" --clean --noconfirm zdhcs.spec

Write-Host ""
Write-Host "打包完成：dist\zdhcs\zdhcs.exe"

