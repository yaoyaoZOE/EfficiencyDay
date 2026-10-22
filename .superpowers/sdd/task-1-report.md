# Task 1 Report: Security Configuration and UTC Date Helpers

## Scope

Implemented Task 1 only:

- Added initial-account and positive session-lifetime settings.
- Added UTC-aware current-time and account-time-zone date helpers.
- Added first-startup environment examples without sample credentials.
- Added `argon2-cffi` as a runtime dependency and refreshed `backend/requirements.lock`.
- Added `tzdata` as a runtime dependency so IANA `ZoneInfo` names work on Windows, which has no system IANA database by default.
- Added the focused configuration and time-helper tests.

No later-task interfaces were added. `docs/archi/EfficiencyDay-development-progress.md` was not changed by this task.

## RED: focused tests before production changes

Command (from the repository root):

```powershell
uv run --project backend --extra dev pytest backend/tests/test_config.py backend/tests/test_time.py -q
```

Relevant output before production changes:

```text
Using CPython 3.14.0 interpreter at: C:\Python314\python.exe
Creating virtual environment at: backend\.venv
...
_____________________ ERROR collecting tests/test_time.py _____________________
...
E   ModuleNotFoundError: No module named 'app.core.time'
...
ERROR backend\tests\test_time.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
```

The test module failed to import because the requested helper did not exist.
Because collection stopped at that import error, the settings test was also run
separately against the requested interpreter before implementation.

Command:

```powershell
$env:UV_PROJECT_ENVIRONMENT = 'D:\PersonalProject\EfficiencyDay\.venv'
uv run --project backend --extra dev --python D:\PersonalProject\EfficiencyDay\.venv\Scripts\python.exe pytest backend/tests/test_config.py -q
```

Expected RED output:

```text
F.                                                                       [100%]
================================== FAILURES ===================================
_________________________ test_auth_settings_defaults _________________________
...
E       AttributeError: 'Settings' object has no attribute 'initial_username'
...
FAILED backend\tests\test_config.py::test_auth_settings_defaults
1 failed, 1 passed in 2.64s
```

The first `uv run` selected Python 3.14 but created a project-local
`backend\.venv`; subsequent test commands explicitly selected the requested
root `.venv`. The generated project-local environment and `backend/uv.lock`
were removed after use.

## Dependency lock refresh

Command:

```powershell
uv pip compile backend\pyproject.toml --extra dev --output-file backend\requirements.lock
```

Relevant output:

```text
Resolved 36 packages in 1.40s
argon2-cffi==25.1.0
argon2-cffi-bindings==26.1.0
cffi==2.1.1
pycparser==3.11
tzdata==2026.5
```

## GREEN: focused tests

Command:

```powershell
$env:UV_PROJECT_ENVIRONMENT = 'D:\PersonalProject\EfficiencyDay\.venv'
uv run --project backend --extra dev --python D:\PersonalProject\EfficiencyDay\.venv\Scripts\python.exe pytest backend/tests/test_config.py backend/tests/test_time.py -q
```

Output:

```text
.....                                                                    [100%]
5 passed in 0.79s
```

## Existing backend suite

Command:

```powershell
$env:UV_PROJECT_ENVIRONMENT = 'D:\PersonalProject\EfficiencyDay\.venv'
uv run --project backend --extra dev --python D:\PersonalProject\EfficiencyDay\.venv\Scripts\python.exe pytest backend/tests -q
```

Output:

```text
...........                                                              [100%]
11 passed in 10.43s
```

Final verification after writing this report:

```powershell
$env:UV_PROJECT_ENVIRONMENT = 'D:\PersonalProject\EfficiencyDay\.venv'
uv run --project backend --extra dev --python D:\PersonalProject\EfficiencyDay\.venv\Scripts\python.exe pytest backend/tests -q
uv run --project backend --extra dev --python D:\PersonalProject\EfficiencyDay\.venv\Scripts\python.exe ruff check backend/app/core/config.py backend/app/core/time.py backend/tests/test_config.py backend/tests/test_time.py
```

Output:

```text
...........                                                              [100%]
11 passed in 3.46s
All checks passed!
```

## Notes

The initial Windows-focused time-zone test exposed that `ZoneInfo` requires
IANA time-zone data on this platform. Adding `tzdata` to runtime dependencies
made the required `Asia/Shanghai` conversion pass without masking invalid zone
names.
