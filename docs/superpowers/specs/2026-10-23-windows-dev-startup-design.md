# Windows Development Startup Script

## Goal

Provide a double-clickable Windows entry point to start the EfficiencyDay frontend and backend for local development.

## Design

Add `start-dev.bat` at the repository root. It resolves paths relative to its own location so it works regardless of the caller's current directory. Before starting servers, it checks for the repository virtual-environment Python, Node.js/npm, `backend\.env`, and whether the documented ports are available. An occupied port produces a clear message and stops startup without terminating any process. It then runs Alembic migrations synchronously from the backend directory. Missing prerequisites or a failed migration also stop startup.

After migrations succeed, the script opens separate visible terminal windows for the backend Uvicorn reload server and frontend Vite server. Each command uses the existing documented loopback addresses and ports. The launcher prints the frontend and API documentation URLs and leaves its own window open long enough for the user to read errors or startup instructions. It does not create or change credentials, install dependencies, modify environment files, or silently choose alternate ports.

## Validation

Validate the batch file's prerequisites and command construction without starting duplicate application servers; verify migrations and the existing health endpoint with the launched services. Preserve existing VS Code tasks and development behavior.
