# Windows Development Startup Script Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a double-clickable Windows batch file that checks prerequisites, migrates the database, and starts the frontend and backend in separate visible terminals.

**Architecture:** Keep startup orchestration in a root-level `start-dev.bat`, resolving every project path relative to `%~dp0`. Run migrations in the launcher synchronously, then use `start` to open separate console windows for the existing Uvicorn and Vite commands. Update README with the new primary Windows startup instructions while retaining the manual and VS Code alternatives.

**Tech Stack:** Windows CMD batch, Python virtual environment, Alembic, Uvicorn, Node.js/npm, Vite.

## Global Constraints

- Use the existing `.venv\Scripts\python.exe`, frontend npm installation, ports 6931 and 8327, and loopback-only bind addresses.
- Require `backend\.env`; do not create, alter, print, or commit secrets.
- Do not install dependencies, terminate existing processes, or silently select alternate ports.
- Stop before launching either server when a prerequisite, port check, or migration fails.
- Preserve the existing VS Code tasks and documented manual startup commands.

---

### Task 1: Add the Windows one-click launcher and document it

**Files:**
- Create: `start-dev.bat`
- Modify: `README.md` (Windows development startup section)

**Interfaces:**
- Consumes: Root `.venv\Scripts\python.exe`, `backend\.env`, Node.js/npm, and the existing backend and frontend startup commands.
- Produces: A root-level batch file that users can double-click; frontend at `http://127.0.0.1:8327/` and API docs at `http://127.0.0.1:6931/docs`.

- [ ] **Step 1: Check that launcher prerequisites are discoverable**

From the repository root, run:

```powershell
Test-Path .\.venv\Scripts\python.exe
Test-Path .\backend\.env
Get-Command node.exe, npm.cmd
```

Expected: the first two commands return `True`, and Node.js/npm resolve. Do not display or read `.env` values.

- [ ] **Step 2: Create `start-dev.bat`**

Use this complete batch file:

```bat
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
```

- [ ] **Step 3: Run static checks on the launcher**

From the repository root, run:

```powershell
$script = Get-Content .\start-dev.bat -Raw
if ($script -notmatch '(?m)^set "ROOT=%~dp0"$') { throw 'Launcher must resolve paths from its own location.' }
if ($script -notmatch 'alembic upgrade head') { throw 'Launcher must apply migrations.' }
if ($script -notmatch 'uvicorn app\.main:app') { throw 'Launcher must start the backend.' }
if ($script -notmatch 'npm\.cmd run dev') { throw 'Launcher must start the frontend.' }
if ($script -notmatch ':6931 .*LISTENING' -or $script -notmatch ':8327 .*LISTENING') { throw 'Launcher must check both ports.' }
'Launcher static checks passed.'
```

Expected: `Launcher static checks passed.`

- [ ] **Step 4: Document the batch launcher**

Update README section `### 3. 启动` to say that double-clicking `start-dev.bat` from Explorer starts both development servers after prerequisite checks and database migrations. Keep the existing VS Code `dev: all` and manual terminal instructions as alternatives, and retain the existing service URLs and local-only security note.

- [ ] **Step 5: Review the final changes**

Run:

```powershell
git diff --check
git diff -- README.md
git status --short
```

Expected: no whitespace errors; the README describes the launcher and alternatives accurately; only `README.md` and `start-dev.bat` are changed by this task. Do not stage unrelated user files.

## Self-Review

- **Spec coverage:** Root-relative paths, checks for Python/Node/npm/configuration and both occupied ports, synchronous Alembic migration, visible backend/frontend console windows, documented URLs, explicit failure messages, no secret handling, and retained VS Code/manual workflows are covered.
- **Placeholder scan:** No TODO, TBD, or unspecified implementation steps.
- **Consistency:** Uses the paths, ports, commands, and loopback addresses in the current README and VS Code task configuration.
