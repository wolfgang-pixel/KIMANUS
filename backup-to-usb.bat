@echo off
REM === KIMANUS OS - Taeglich Backup auf USB-Stick (D:\) ===
REM Doppelklick auf diese Datei = Backup starten

set DATUM=%date:~6,4%-%date:~3,2%-%date:~0,2%
set ZEIT=%time:~0,2%%time:~3,2%
set BACKUP_DIR=D:\KIMANUS-Backup\%DATUM%

echo.
echo ============================================
echo   KIMANUS OS BACKUP - %DATUM% %ZEIT%
echo ============================================
echo.

REM Backup-Ordner erstellen
if not exist "D:\KIMANUS-Backup" mkdir "D:\KIMANUS-Backup"
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

echo [1/4] Lokale App-Dateien sichern...
if not exist "%BACKUP_DIR%\kimanus-app" mkdir "%BACKUP_DIR%\kimanus-app"
xcopy /Y /Q "C:\Users\wolfg\kimanus-app\*.*" "%BACKUP_DIR%\kimanus-app\" >nul 2>&1
echo       OK - index.html, server.py, Dockerfile, etc.

echo [2/4] Server-Dateien vom Server holen...
scp -i "C:\Users\wolfg\.ssh\id_ed25519" -r root@31.97.216.22:/root/litellm-gateway/kimanus-app/ "%BACKUP_DIR%\server-kimanus-app\" >nul 2>&1
echo       OK - Server-Version der App

echo [3/4] Server-Konfiguration sichern...
if not exist "%BACKUP_DIR%\server-config" mkdir "%BACKUP_DIR%\server-config"
scp -i "C:\Users\wolfg\.ssh\id_ed25519" root@31.97.216.22:/root/litellm-gateway/docker-compose.yml "%BACKUP_DIR%\server-config\" >nul 2>&1
scp -i "C:\Users\wolfg\.ssh\id_ed25519" root@31.97.216.22:/root/litellm-gateway/litellm_config.yaml "%BACKUP_DIR%\server-config\" >nul 2>&1
scp -i "C:\Users\wolfg\.ssh\id_ed25519" root@31.97.216.22:/root/litellm-gateway/Caddyfile "%BACKUP_DIR%\server-config\" >nul 2>&1
scp -i "C:\Users\wolfg\.ssh\id_ed25519" -r root@31.97.216.22:/root/litellm-gateway/openclaw-data/workspace/ "%BACKUP_DIR%\server-config\workspace\" >nul 2>&1
echo       OK - docker-compose, LiteLLM, Caddy, Workspace/Memory

echo [4/4] Manus-Bot sichern...
scp -i "C:\Users\wolfg\.ssh\id_ed25519" -r root@31.97.216.22:/root/litellm-gateway/manus-bot/ "%BACKUP_DIR%\manus-bot\" >nul 2>&1
echo       OK - Manus Matrix Bot

echo.
echo ============================================
echo   BACKUP FERTIG!
echo   Gespeichert in: %BACKUP_DIR%
echo ============================================
echo.

REM Alte Backups aufraumen (behalte letzte 14 Tage)
forfiles /p "D:\KIMANUS-Backup" /d -14 /c "cmd /c if @isdir==TRUE rmdir /s /q @path" >nul 2>&1

echo Alte Backups (aelter als 14 Tage) wurden bereinigt.
echo.
pause
