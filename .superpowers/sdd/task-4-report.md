# Task 4 Report: Session-Backed Authentication and CSRF

**Status:** Complete
**Commit:** `17c94cf17e8d888c6c90a44409c8b950754850b6` (`feat: add revocable cookie sessions`)

## Implementation

- Added Argon2id password hashing and verification, opaque URL-safe tokens, and SHA-256 token hashing.
- Added authentication/session services. Successful authentication persists only the session-token hash, stores an independent CSRF token, and uses the configured session TTL. Revocation writes `revoked_at`.
- Added dependencies that reject missing, expired, or revoked sessions and compare CSRF tokens in constant time. Unsafe requests also require an `Origin` matching the effective ASGI request origin.
- Added login, current-user, and logout endpoints. Session cookies are `HttpOnly`, `Secure`, `SameSite=Lax`, and scoped to `/`; logout revokes the server-side record and clears the cookie.
- Registered the authentication router under `/api/v1`.
- Added focused HTTPS `TestClient` coverage for password handling, generic credential errors, cookie properties, persisted token hashes, `/me`, CSRF/origin rejection, logout revocation, and session expiry.

No work-item endpoints, Nginx rate limiting, database migration, or unrelated documentation was changed. Only the eight Task 4 code/test paths were staged and committed. Existing unrelated untracked documentation and planning files were left untouched.

## TDD Evidence

### RED

Wrote `backend/tests/test_auth.py` before adding production authentication code, then ran:

```text
uv run --python D:\PersonalProject\EfficiencyDay\.venv\Scripts\python.exe --project backend --extra dev pytest backend/tests/test_auth.py -q
```

Expected failure was observed: all seven tests failed, beginning with `ModuleNotFoundError: No module named 'app.core.security'`; the authentication schemas, services, dependencies, and routes were not yet present.

### GREEN

After implementation, the first focused run exposed one test setup error: its revocation check selected the first session row, not the row matching the newly issued token. The test was corrected to select by the token hash. The focused auth suite then passed:

```text
7 passed in 6.66s
```

## Final Verification

All commands used the Python 3.14 interpreter at `D:\PersonalProject\EfficiencyDay\.venv\Scripts\python.exe` with `UV_PROJECT_ENVIRONMENT=D:\PersonalProject\EfficiencyDay\.venv`.

| Validation | Result |
| --- | --- |
| Auth + bootstrap + health tests | `21 passed in 15.40s` |
| Full backend test suite | `34 passed in 17.14s` |
| Ruff check (`backend`) | `All checks passed!` |
| `git diff --check` | Passed |

The root `.venv` was used; `backend/.venv` and `backend/uv.lock` are absent. The `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>` trailer is present in the commit.

## Concern

Same-origin validation uses `request.base_url` from the effective ASGI scope. In a TLS-terminating reverse-proxy deployment, Uvicorn must be configured to honor forwarded headers only from trusted proxy addresses; otherwise the ASGI scheme/host may not reflect the browser-facing origin. Proxy deployment configuration was not changed as part of Task 4.

## Important review finding: explicit trusted public origin

**Status:** Fixed
**Design:** Approved in `2c2cff3`
**Fix commit:** See the follow-up commit containing this report and the origin validation changes.

- Added `Settings.public_origin: AnyHttpUrl | None`, treating blank values as absent and rejecting configured paths, queries, or fragments.
- Login and authenticated unsafe requests now compare the request `Origin` against the single configured public origin. The comparison normalizes scheme and host case, IDN hostnames, IP literals, and default ports.
- Missing configuration fails closed with HTTP 503. No request host, ASGI URL, or forwarded header is used to derive the trusted origin.
- Wired `EFFICIENCYDAY_PUBLIC_ORIGIN` through Compose and both env examples.
- Added coverage for missing configuration (login and logout), mismatched origins, and an external HTTPS origin accepted by an internal HTTP ASGI request without forwarded headers. Existing auth behavior remains covered.

### TDD evidence

**RED**, before production changes:

```powershell
$env:UV_PROJECT_ENVIRONMENT='D:\PersonalProject\EfficiencyDay\.venv'
& 'D:\PersonalProject\EfficiencyDay\.venv\Scripts\python.exe' -m pytest backend/tests/test_auth.py backend/tests/test_config.py -q --tb=no
```

```text
11 failed, 3 passed in 5.15s
```

The intended failures showed that `Settings.public_origin` and the required origin checks were not implemented.

**GREEN**, after implementation (same Python 3.14 interpreter and `UV_PROJECT_ENVIRONMENT`):

```powershell
$env:UV_PROJECT_ENVIRONMENT='D:\PersonalProject\EfficiencyDay\.venv'
& 'D:\PersonalProject\EfficiencyDay\.venv\Scripts\python.exe' -m pytest backend/tests/test_auth.py -q
# 10 passed in 11.73s

& 'D:\PersonalProject\EfficiencyDay\.venv\Scripts\python.exe' -m pytest backend/tests/test_config.py -q
# 4 passed in 1.10s

& 'D:\PersonalProject\EfficiencyDay\.venv\Scripts\python.exe' -m pytest backend/tests -q
# 39 passed in 22.61s

& 'D:\PersonalProject\EfficiencyDay\.venv\Scripts\python.exe' -m ruff check backend
# All checks passed!

git diff --check
# Passed
```

The old proxy-dependent-origin concern above is superseded: browser-origin validation now uses only the explicit public-origin setting.
