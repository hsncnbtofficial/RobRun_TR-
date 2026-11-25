@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title ROB RUN Türkçe - Kurulum

echo ==============================================
echo   ROB RUN TÜRKÇE  -  açık kaynak Türkçe yama
echo ==============================================
echo.

rem ---------- 1) uv (Python paket yöneticisi) ----------
set "PATH=%USERPROFILE%\.local\bin;%LOCALAPPDATA%\Microsoft\WinGet\Links;%PATH%"
where uv >nul 2>nul
if errorlevel 1 (
    echo [1/2] uv bulunamadı, winget ile kuruluyor...
    winget install --id astral-sh.uv -e --accept-source-agreements --accept-package-agreements
    where uv >nul 2>nul
    if errorlevel 1 (
        echo.
        echo uv kurulamadı. Lütfen https://docs.astral.sh/uv/ adresinden uv'yi kurup
        echo bu dosyayı tekrar çalıştırın.
        pause
        exit /b 1
    )
) else (
    echo [1/2] uv hazır.
)

rem ---------- 2) Python + bağımlılıklar ----------
echo [2/2] Python ve kütüphaneler hazırlanıyor (ilk seferde birkaç dakika sürebilir)...
uv sync
if errorlevel 1 (
    echo Kütüphaneler kurulamadı. İnternet bağlantınızı kontrol edin.
    pause
    exit /b 1
)

:menu
echo.
echo ----------------------------------------------
echo   1) Programı aç (önerilen: yama + rehber)
echo   2) Türkçe yamayı kur ve oyunu başlat
echo   3) Türkçe yamayı kaldır (oyun İngilizceye döner)
echo   4) Kurulum dosyası derle (release\RobRun_Turkce_Setup.exe)
echo   5) Çıkış
echo ----------------------------------------------
set "secim="
set /p secim="Seçiminiz [1-5]: "

if "%secim%"=="1" (
    start "" uv run pythonw app\main.py
    goto :eof
)
if "%secim%"=="2" (
    uv run python robrun_tr\fonts.py || goto :hata
    uv run python robrun_tr\build.py --no-fold || goto :hata
    uv run python robrun_tr\install.py --fonts --launch || goto :hata
    goto :menu
)
if "%secim%"=="3" (
    uv run python robrun_tr\install.py --uninstall
    goto :menu
)
if "%secim%"=="4" (
    powershell -NoProfile -ExecutionPolicy Bypass -File tools\build_release.ps1 || goto :hata
    goto :menu
)
if "%secim%"=="5" goto :eof
echo Geçersiz seçim.
goto :menu

:hata
echo.
echo Bir hata oluştu. Yukarıdaki mesajı kontrol edin.
pause
goto :menu
