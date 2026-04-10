@echo off
REM ============================================================
REM IsotopeIQ Windows Agent Installer
REM Registers the agent as a scheduled task that runs at system
REM startup under SYSTEM — no third-party dependencies required.
REM
REM Usage (from an elevated Administrator command prompt):
REM   windows_install.bat [path-to-binary]
REM
REM The binary is included in the ZIP downloaded from IsotopeIQ.
REM Pass an explicit path only if placing the binary elsewhere.
REM ============================================================

setlocal EnableDelayedExpansion

REM Load defaults from agent.conf if bundled alongside this script.
set PORT=9322
set SECRET=
set "_CONF=%~dp0agent.conf"
if exist "!_CONF!" (
    for /f "usebackq tokens=1,* delims==" %%A in ("!_CONF!") do (
        if "%%A"=="PORT"   set PORT=%%B
        if "%%A"=="SECRET" set SECRET=%%B
    )
)

set /p PORT_INPUT="Port to listen on [%PORT%]: "
if not "!PORT_INPUT!"=="" set PORT=!PORT_INPUT!
echo Using port: %PORT%
if not "!SECRET!"=="" echo Agent secret authentication enabled.

REM ---- Locate binary ----
set BINARY=%~1
if "!BINARY!"=="" (
    if exist "%~dp0windows_collector.exe" (
        set BINARY=%~dp0windows_collector.exe
    ) else (
        echo ERROR: Binary not found. Place windows_collector.exe alongside this script.
        exit /b 1
    )
)

set TASK_NAME=IsotopeIQAgent
set INSTALL_DIR=C:\Program Files\IsotopeIQ
set INSTALL_PATH=%INSTALL_DIR%\isotopeiq-agent.exe
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

REM ---- Create log directory ----
if not exist "%LOG_DIR%\" mkdir "%LOG_DIR%"

REM ---- Build agent command line ----
set _AGENT_CMD="!INSTALL_PATH!" --serve --port !PORT!
if not "!SECRET!"=="" set _AGENT_CMD=!_AGENT_CMD! --secret !SECRET!

REM ---- Register the scheduled task ----
REM   /sc ONSTART  : trigger at every system boot (before any user logs in)
REM   /ru SYSTEM   : run as LocalSystem — no password needed, survives user logoff
REM   /rl HIGHEST  : highest privilege level
REM   /f           : overwrite if task already exists (belt-and-suspenders)
echo Registering scheduled task: %TASK_NAME%
schtasks /create ^
    /tn "%TASK_NAME%" ^
    /tr "!_AGENT_CMD!" ^
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

echo.
echo Done.  Agent listening on 0.0.0.0:!PORT!
if not "!SECRET!"=="" echo        Agent secret authentication enabled.
echo Check status:  schtasks /query /tn "%TASK_NAME%" /fo LIST /v
echo View logs:     type "%LOG_DIR%\isotopeiq-agent.log"
endlocal
