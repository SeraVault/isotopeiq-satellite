@echo off
REM ============================================================
REM IsotopeIQ Windows Agent Installer
REM Installs the agent as a Windows Service using NSSM.
REM The agent self-enrolls with the satellite on first install;
REM the device-specific token is saved to
REM C:\ProgramData\IsotopeIQ\agent.token and never appears in
REM service parameters.
REM
REM Requirements:
REM   - Run from an elevated (Administrator) command prompt
REM   - NSSM must be on PATH or in the same directory as this script
REM     Download: https://nssm.cc/download
REM
REM Usage:
REM   install-service.bat <enrollment-token> <satellite-url> [port] [path-to-binary]
REM
REM   enrollment-token : system-wide enrollment secret from the satellite admin panel
REM   satellite-url    : base URL of the satellite, e.g. https://satellite.example.com
REM   port             : TCP listen port (default: 9322)
REM   path-to-binary   : path to windows_collector.exe
REM                      (default: windows_collector.exe in the current directory)
REM ============================================================

setlocal EnableDelayedExpansion

REM ---- Argument validation ----
if "%~1"=="" (
    echo ERROR: enrollment-token is required.
    echo Usage: install-service.bat ^<enrollment-token^> ^<satellite-url^> [port] [binary]
    exit /b 1
)
if "%~2"=="" (
    echo ERROR: satellite-url is required.
    echo Usage: install-service.bat ^<enrollment-token^> ^<satellite-url^> [port] [binary]
    exit /b 1
)

set ENROLLMENT_TOKEN=%~1
set SATELLITE=%~2
set PORT=%~3
if "!PORT!"=="" set PORT=9322

set BINARY=%~4
if "!BINARY!"=="" set BINARY=%~dp0windows_collector.exe

if not exist "!BINARY!" (
    echo ERROR: Binary not found: !BINARY!
    exit /b 1
)

REM ---- Locate NSSM ----
set NSSM=nssm.exe
where nssm.exe >nul 2>&1
if errorlevel 1 (
    if exist "%~dp0nssm.exe" (
        set NSSM=%~dp0nssm.exe
    ) else (
        echo ERROR: nssm.exe not found on PATH or in the installer directory.
        echo Download from https://nssm.cc/download and place it alongside this script.
        exit /b 1
    )
)

set SERVICE_NAME=IsotopeIQAgent
set INSTALL_PATH=C:\Program Files\IsotopeIQ\isotopeiq-agent.exe
set LOG_DIR=C:\ProgramData\IsotopeIQ\logs

REM ---- Copy binary ----
if not exist "C:\Program Files\IsotopeIQ\" mkdir "C:\Program Files\IsotopeIQ\"
echo Copying binary to %INSTALL_PATH%
copy /Y "!BINARY!" "%INSTALL_PATH%" >nul

REM ---- Create log directory ----
if not exist "%LOG_DIR%\" mkdir "%LOG_DIR%"

REM ---- Enroll with satellite ----
echo Enrolling with satellite at !SATELLITE! ...
"%INSTALL_PATH%" --enroll --satellite "!SATELLITE!" --enrollment-token "!ENROLLMENT_TOKEN!" --port !PORT!
if errorlevel 1 (
    echo ERROR: Enrollment failed. Verify the satellite URL and enrollment token.
    exit /b 1
)

REM ---- Remove existing service if present ----
%NSSM% status %SERVICE_NAME% >nul 2>&1
if not errorlevel 1 (
    echo Removing existing %SERVICE_NAME% service...
    %NSSM% stop %SERVICE_NAME% confirm >nul 2>&1
    %NSSM% remove %SERVICE_NAME% confirm
)

REM ---- Install the service ----
echo Installing service: %SERVICE_NAME%
%NSSM% install %SERVICE_NAME% "%INSTALL_PATH%"
%NSSM% set %SERVICE_NAME% AppParameters "--serve --port !PORT!"
%NSSM% set %SERVICE_NAME% DisplayName "IsotopeIQ Baseline Collection Agent"
%NSSM% set %SERVICE_NAME% Description "Listens on port !PORT! for baseline collection requests from an IsotopeIQ satellite."
%NSSM% set %SERVICE_NAME% Start SERVICE_AUTO_START
%NSSM% set %SERVICE_NAME% ObjectName LocalSystem
%NSSM% set %SERVICE_NAME% AppStdout "%LOG_DIR%\isotopeiq-agent.log"
%NSSM% set %SERVICE_NAME% AppStderr "%LOG_DIR%\isotopeiq-agent.log"
%NSSM% set %SERVICE_NAME% AppRotateFiles 1
%NSSM% set %SERVICE_NAME% AppRotateBytes 10485760

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

REM ---- Start the service ----
echo Starting %SERVICE_NAME%...
%NSSM% start %SERVICE_NAME%

echo.
echo Done.  Agent enrolled and listening on 0.0.0.0:!PORT!
echo Check status:  sc query %SERVICE_NAME%
echo View logs:     type "%LOG_DIR%\isotopeiq-agent.log"
endlocal

%NSSM% set %SERVICE_NAME% ObjectName LocalSystem
%NSSM% set %SERVICE_NAME% AppStdout "%LOG_DIR%\isotopeiq-agent.log"
%NSSM% set %SERVICE_NAME% AppStderr "%LOG_DIR%\isotopeiq-agent.log"
%NSSM% set %SERVICE_NAME% AppRotateFiles 1
%NSSM% set %SERVICE_NAME% AppRotateBytes 10485760

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

REM ---- Start the service ----
echo Starting %SERVICE_NAME%...
%NSSM% start %SERVICE_NAME%

echo.
echo Done.  Agent is listening on 0.0.0.0:!PORT!
echo Check status:  sc query %SERVICE_NAME%
echo View logs:     type "%LOG_DIR%\isotopeiq-agent.log"
endlocal
