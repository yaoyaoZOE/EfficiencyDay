@echo off
setlocal
set "ROOT=%~dp0"
set "PYTHON=%ROOT%.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo [ERROR] Python virtual environment not found: "%PYTHON%"
    echo Create it and install backend dependencies as described in README.md.
    goto :failure
)

if not exist "%ROOT%backend\.env" (
    echo [ERROR] Backend configuration not found: "%ROOT%backend\.env"
    echo Copy backend\.env.example to backend\.env and configure it first.
    goto :failure
)

where node.exe >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Node.js was not found on PATH.
    goto :failure
)

where npm.cmd >nul 2>nul
if errorlevel 1 (
    echo [ERROR] npm was not found on PATH.
    goto :failure
)

netstat -ano -p tcp | findstr /R /C:":6931 .*LISTENING" >nul
if not errorlevel 1 (
    echo [ERROR] Port 6931 is already in use. Stop its existing service and retry.
    goto :failure
)

netstat -ano -p tcp | findstr /R /C:":8327 .*LISTENING" >nul
if not errorlevel 1 (
    echo [ERROR] Port 8327 is already in use. Stop its existing service and retry.
    goto :failure
)

echo [INFO] Applying database migrations...
pushd "%ROOT%backend"
"%PYTHON%" -m alembic upgrade head
if errorlevel 1 (
    popd
    echo [ERROR] Database migration failed. Servers were not started.
    goto :failure
)
popd

echo [INFO] Starting backend and frontend...
start "EfficiencyDay Backend" /D "%ROOT%backend" "%PYTHON%" -m uvicorn app.main:app --host 127.0.0.1 --port 6931 --reload
start "EfficiencyDay Frontend" /D "%ROOT%frontend" cmd.exe /k npm.cmd run dev

echo.
echo Frontend:  http://127.0.0.1:8327/
echo API docs:  http://127.0.0.1:6931/docs
echo Close the two service windows to stop the development servers.
pause
exit /b 0

:failure
echo.
pause
exit /b 1
