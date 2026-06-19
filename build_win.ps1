# Build "Drive Downloader" for Windows (PowerShell).
# Run ON a Windows machine (PyInstaller can't cross-compile from macOS).
#
# Prerequisites on Windows:
#   - Python 3.10–3.12 from python.org (tick "Add to PATH")
#   - rclone.exe must sit next to this script (already included in the repo)
#
# Usage (in PowerShell, from the project folder):
#   powershell -ExecutionPolicy Bypass -File .\build_win.ps1

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

Write-Host "==> 1/3  Python venv + dependencies"
if (-not (Test-Path ".venv")) { python -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\pip.exe install -r requirements.txt pyinstaller pillow

Write-Host "==> 2/3  Icon + build .exe (PyInstaller)"
& .\.venv\Scripts\python.exe make_icon.py
if (-not (Test-Path "rclone.exe")) {
  Write-Host "    rclone.exe missing — downloading rclone for windows-amd64…"
  $zip = "$env:TEMP\rclone-win.zip"
  Invoke-WebRequest -Uri "https://downloads.rclone.org/rclone-current-windows-amd64.zip" -OutFile $zip
  Expand-Archive -Path $zip -DestinationPath "$env:TEMP\rclone-win" -Force
  $exe = Get-ChildItem -Path "$env:TEMP\rclone-win" -Recurse -Filter rclone.exe | Select-Object -First 1
  Copy-Item $exe.FullName -Destination ".\rclone.exe"
}
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
& .\.venv\Scripts\pyinstaller.exe --noconfirm --windowed --name "Drive Downloader" `
  --icon icon.ico `
  --add-data "ui;ui" `
  --add-binary "rclone.exe;." `
  --collect-all webview `
  --collect-all certifi --hidden-import certifi `
  app.py

Write-Host "==> 3/3  Done"
Write-Host "    Portable app : dist\Drive Downloader\Drive Downloader.exe"
Write-Host ""
Write-Host "    To make an installer (Setup.exe): install Inno Setup, then run:"
Write-Host "        & 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe' installer.iss"
