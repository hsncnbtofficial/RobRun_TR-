# Builds the release: dist\RobRun_Turkce.exe (app) and release\RobRun_Turkce_Setup.exe (installer wizard).
# Usage (from the project folder):  powershell -ExecutionPolicy Bypass -File tools\build_release.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "== 1/3 Program (RobRun_Turkce.exe)"
uv run pyinstaller --noconfirm --onefile --windowed --name RobRun_Turkce --icon "..\assets\icon.ico" `
  --distpath build_tmp\appdist --workpath build_tmp\app --specpath build_tmp `
  --paths robrun_tr --hidden-import build --hidden-import fonts --hidden-import install --hidden-import common --hidden-import extract --hidden-import live --hidden-import winpaths --hidden-import mss --hidden-import psutil `
  --collect-all UnityPy --collect-all archspec --collect-all fmod_toolkit --collect-all pyfmodex `
  --collect-all texture2ddecoder --collect-all etcpak --collect-all astc_encoder --collect-all winrt --collect-submodules webview `
  --add-data "..\app\ui;app\ui" --add-data "..\data\guide.json;data" --add-data "..\data\strings_tr.json;data" `
  --add-data "..\data\strings_overlay.json;data" app\main.py
if ($LASTEXITCODE -ne 0) { throw "program derlemesi başarısız" }

Write-Host "== 2/3 Kurulum içeriği"
$payload = Join-Path $root "build_tmp\payload"
Remove-Item $payload -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $payload | Out-Null
Copy-Item build_tmp\appdist\RobRun_Turkce.exe, installer\BENI_OKU.txt, assets\icon.ico $payload
# refresh the loose copy in dist\ too, unless that exe is currently open
try { Copy-Item build_tmp\appdist\RobRun_Turkce.exe dist\RobRun_Turkce.exe -Force } catch { Write-Host "(dist\RobRun_Turkce.exe açık, güncellenmedi)" }

Write-Host "== 3/3 Kurulum sihirbazı (RobRun_Turkce_Setup.exe)"
uv run pyinstaller --noconfirm --onefile --windowed --name RobRun_Turkce_Setup --icon "..\assets\icon.ico" `
  --distpath release --workpath build_tmp\setup --specpath build_tmp `
  --paths robrun_tr --hidden-import winpaths --hidden-import win32com.client --hidden-import pythoncom --add-data "payload;payload" installer\setup.py
if ($LASTEXITCODE -ne 0) { throw "kurulum derlemesi başarısız" }
Get-Item release\RobRun_Turkce_Setup.exe | Select-Object FullName, Length
