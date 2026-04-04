@echo off
REM ============================================================
REM IsotopeIQ Windows Agent Installer
REM Registers the agent as a scheduled task that runs at system
REM startup under SYSTEM — no third-party dependencies required.
REM
REM Workflow:
REM   1. Add the device in IsotopeIQ and download isotopeiq-agent.conf.
REM   2. Place isotopeiq-agent.conf in the same folder as this script.
REM   3. Run from an elevated (Administrator) command prompt:
REM        windows_install.bat [config-file] [path-to-binary]
REM
REM Arguments:
REM   config-file    : path to isotopeiq-agent.conf
REM                    (default: isotopeiq-agent.conf in the script directory)
REM   path-to-binary : path to windows_collector.exe
REM                    (default: windows_collector.exe in the script directory)
REM ============================================================

setlocal EnableDelayedExpansion

REM ---- Locate config file ----
set CONFIG_FILE=%~1
if "!CONFIG_FILE!"=="" set CONFIG_FILE=%~dp0isotopeiq-agent.conf

if not exist "!CONFIG_FILE!" (
    echo ERROR: Config file not found: !CONFIG_FILE!
    echo Download isotopeiq-agent.conf from IsotopeIQ and place it alongside this script.
    exit /b 1
)

REM ---- Parse config file ----
set PORT=
set SERVER=
for /f "usebackq tokens=1,* delims==" %%a in ("!CONFIG_FILE!") do (
    if "%%a"=="port"   set PORT=%%b
    if "%%a"=="server" set SERVER=%%b
)
if "!PORT!"=="" set PORT=9322

REM ---- Locate or download binary ----
set BINARY=%~2
set CLEANUP_BIN=0
if "!BINARY!"=="" (
    if exist "%~dp0windows_collector.exe" (
        set BINARY=%~dp0windows_collector.exe
    ) else if not "!SERVER!"=="" (
        echo Downloading windows_collector.exe from !SERVER!...
        set DOWNLOAD_TMP=%TEMP%\isotopeiq_agent_dl.exe
        powershell -NoProfile -ExecutionPolicy Bypass -Command ^
            "$url = '!SERVER!/api/agents/windows_collector.exe';" ^
            "$out = '!DOWNLOAD_TMP!';" ^
            "(New-Object System.Net.WebClient).DownloadFile($url, $out);" ^
            "$infoJson = (New-Object System.Net.WebClient).DownloadString('!SERVER!/api/agents/windows_collector.exe/info');" ^
            "$info = ConvertFrom-Json $infoJson;" ^
            "$actual = (Get-FileHash $out -Algorithm SHA256).Hash.ToLower();" ^
            "if ($actual -ne $info.sha256) { Remove-Item $out -Force; throw ('SHA-256 mismatch: expected ' + $info.sha256 + ', got ' + $actual) }"
        if errorlevel 1 (
            echo ERROR: Binary download or SHA-256 verification failed.
            exit /b 1
        )
        echo SHA-256 verified.
        set BINARY=!DOWNLOAD_TMP!
        set CLEANUP_BIN=1
    ) else (
        echo ERROR: Binary not found locally and no 'server' in !CONFIG_FILE! to download from.
        exit /b 1
    )
)

set TASK_NAME=IsotopeIQAgent
set INSTALL_DIR=C:\Program Files\IsotopeIQ
set INSTALL_PATH=%INSTALL_DIR%\isotopeiq-agent.exe
set CONFIG_DEST=C:\ProgramData\IsotopeIQ\agent.conf
set LOG_DIR=C:\ProgramData\IsotopeIQ\logs

REM ---- Stop and remove any existing installation ----
schtasks /query /tn "%TASK_NAME%" >nul 2>&1
if not errorlevel 1 (
    echo Stopping existing scheduled task %TASK_NAME%...
    schtasks /end /tn "%TASK_NAME%" >nul 2>&1
    schtasks /delete /tn "%TASK_NAME%" /f >nul
)
taskkill /f /im isotopeiq-agent.exe >nul 2>&1
timeout /t 2 /nobreak >nul

REM ---- Copy binary ----
if not exist "%INSTALL_DIR%\" mkdir "%INSTALL_DIR%"
echo Copying binary to %INSTALL_PATH%
copy /Y "!BINARY!" "%INSTALL_PATH%" >nul

REM ---- Install config file ----
if not exist "C:\ProgramData\IsotopeIQ\" mkdir "C:\ProgramData\IsotopeIQ"
REM Reset ACL before copying so reinstalls can overwrite a previously locked config
if exist "%CONFIG_DEST%" icacls "%CONFIG_DEST%" /reset >nul 2>&1
echo Installing config to %CONFIG_DEST%
copy /Y "!CONFIG_FILE!" "%CONFIG_DEST%" >nul
REM Restrict read access to SYSTEM and Administrators only
icacls "%CONFIG_DEST%" /inheritance:r /grant:r "SYSTEM:(R)" "Administrators:(R)" >nul

REM ---- Create log directory ----
if not exist "%LOG_DIR%\" mkdir "%LOG_DIR%"

REM ---- Register the scheduled task ----
REM   /sc ONSTART  : trigger at every system boot (before any user logs in)
REM   /ru SYSTEM   : run as LocalSystem — no password needed, survives user logoff
REM   /rl HIGHEST  : highest privilege level
REM   /f           : overwrite if task already exists (belt-and-suspenders)
echo Registering scheduled task: %TASK_NAME%
schtasks /create ^
    /tn "%TASK_NAME%" ^
    /tr "\"!INSTALL_PATH!\" --serve --port !PORT!" ^
    /sc ONSTART ^
    /ru SYSTEM ^
    /rl HIGHEST ^
    /f
if errorlevel 1 (
    echo ERROR: Failed to register scheduled task.
    exit /b 1
)

REM ---- Open firewall port ----
echo Adding inbound firewall rule for port !PORT!/TCP
netsh advfirewall firewall delete rule name="IsotopeIQ Agent" >nul 2>&1
netsh advfirewall firewall add rule ^
    name="IsotopeIQ Agent" ^
    dir=in ^
    action=allow ^
    protocol=TCP ^
    localport=!PORT! ^
    profile=domain,private ^
    description="IsotopeIQ baseline collection agent"

REM ---- Start immediately without requiring a reboot ----
echo Starting %TASK_NAME%...
schtasks /run /tn "%TASK_NAME%"

if "!CLEANUP_BIN!"=="1" del /f /q "!DOWNLOAD_TMP!" >nul 2>&1

echo.
echo Done.  Agent listening on 0.0.0.0:!PORT!
echo Check status:  schtasks /query /tn "%TASK_NAME%" /fo LIST /v
echo View logs:     type "%LOG_DIR%\isotopeiq-agent.log"
endlocal
