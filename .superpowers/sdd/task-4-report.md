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

## Remaining Task 4 review fixes (2026-10-22)

**Status:** Fixed and verified.
**Fix commit:** The follow-up commit containing this section.
**Starting HEAD:** `142fe93` (the approved brief update following implementation through `a60acac`).

### Scope and implementation

- Compose now forwards `EFFICIENCYDAY_SESSION_TTL_DAYS` with `${EFFICIENCYDAY_SESSION_TTL_DAYS:-7}`. Both env examples document the positive lifetime and default of 7 days.
- Authentication selects either the user's stored hash or a fixed valid dummy Argon2id hash, then calls `verify_password` exactly once before testing user existence and the verification result. The dummy was generated once with `PasswordHasher()` defaults (`m=65536,t=3,p=4`); it is not generated per request. Unknown users and wrong passwords still receive the same generic 401 and create no session or cookie.
- Public-origin configuration rejects username/password userinfo in both raw strings and already parsed `AnyHttpUrl` values. Raw strings with empty userinfo are also rejected before URL normalization can discard it.
- No changes were made to configured-origin matching, forwarded-header handling, successful login, cookie attributes, session revocation, migrations, or database configuration.

### Tests added

- A `patch.object(..., wraps=auth.verify_password)` spy delegates to the real verifier. Unknown users (including with the real admin password) and a known user with a wrong password each invoke verification once. The tests also validate the hash with real Argon2, compare its parameters with the stored hash, check generic 401 details, and assert that no session record or cookie is created.
- Eight userinfo cases cover username-only, username/password, password-only, empty credential components, and parsed URL inputs.
- TTL coverage checks the Compose backend mapping, both env examples, environment-to-Settings loading, and persisted session expiry using the explicitly configured one-day lifetime.
- All authentication database paths remain under pytest's `tmp_path`; migration helpers target those isolated databases. No development database was migrated or used.

### RED: tests before production edits

The editor test runner reported `No tests found in the files. Ensure the correct absolute paths are passed to the tool.` The requested interpreter was then used directly for all recorded test runs.

```powershell
$env:UV_PROJECT_ENVIRONMENT='D:\PersonalProject\EfficiencyDay\.venv'
& 'D:\PersonalProject\EfficiencyDay\.venv\Scripts\python.exe' -m pytest backend\tests\test_auth.py backend\tests\test_config.py -q --tb=short
```

Exact result:

```text
12 failed, 17 passed in 14.05s
```

Exit code: **1**. All 12 failures were the intended missing behavior:

- Two unknown-user cases: `AssertionError: Expected 'verify_password' to have been called once. Called 0 times.`
- Eight userinfo inputs: `Failed: DID NOT RAISE ValidationError`.
- Compose forwarding assertion failed because its backend environment lacked the TTL entry.
- Root env example assertion failed because it lacked `EFFICIENCYDAY_SESSION_TTL_DAYS=7`.

The existing backend env example, Settings environment loading, known-user verification, session TTL persistence, and prior auth/origin behavior passed in RED. No production file was edited until this run completed.

### GREEN and regression verification

All Python commands below used Python **3.14.0** at the requested root `.venv`, with `UV_PROJECT_ENVIRONMENT=D:\PersonalProject\EfficiencyDay\.venv`.

```powershell
& 'D:\PersonalProject\EfficiencyDay\.venv\Scripts\python.exe' -m pytest backend\tests\test_auth.py backend\tests\test_config.py -q --tb=short
```

```text
.............................                                            [100%]
29 passed in 14.73s
```

```powershell
& 'D:\PersonalProject\EfficiencyDay\.venv\Scripts\python.exe' -m pytest backend\tests\test_auth.py -q
```

```text
.............                                                            [100%]
13 passed in 15.56s
```

```powershell
& 'D:\PersonalProject\EfficiencyDay\.venv\Scripts\python.exe' -m pytest backend\tests\test_config.py -q
```

```text
................                                                         [100%]
16 passed in 0.54s
```

```powershell
& 'D:\PersonalProject\EfficiencyDay\.venv\Scripts\python.exe' -m pytest backend\tests -q
```

```text
......................................................                   [100%]
54 passed in 23.97s
```

```powershell
& 'D:\PersonalProject\EfficiencyDay\.venv\Scripts\python.exe' -m ruff check backend
```

```text
All checks passed!
```

All GREEN/regression commands exited **0**. `git diff --check` also exited **0** with no output. The editor Problems check returned `No errors found` for all five changed Python files.

### Compose config validation

Docker/Compose was not installed or on PATH. The initial `docker compose version` failed with `The term 'docker' is not recognized`. An attempt to download the official standalone release with `gh release download` returned `401 Unauthorized`; downloading the public release URLs with `curl.exe` succeeded.

The temporary official `docker/compose` v5.6.1 Windows x86-64 binary was checked against its published SHA-256 file before execution:

```text
Official Compose SHA256 verified
Docker Compose version v5.6.1
```

The standalone binary was used only for configuration validation, without a Docker daemon, image builds, or container startup. With `$compose` pointing at that binary, these commands were run:

```powershell
Remove-Item Env:EFFICIENCYDAY_SESSION_TTL_DAYS -ErrorAction SilentlyContinue
& $compose --env-file .env.example -f docker-compose.yml config --quiet
# The following JSON configurations were parsed with ConvertFrom-Json and
# checked with explicit throwing assertions on services.backend.environment.
& $compose --env-file .env.example -f docker-compose.yml config --format json
& $compose --env-file NUL -f docker-compose.yml config --format json
$env:EFFICIENCYDAY_SESSION_TTL_DAYS='3'
$env:EFFICIENCYDAY_PUBLIC_ORIGIN='https://app.example:8443'
& $compose --env-file NUL -f docker-compose.yml config --format json
$env:EFFICIENCYDAY_SESSION_TTL_DAYS=''
& $compose --env-file NUL -f docker-compose.yml config --format json
```

Exact assertion output (exit code **0**):

```text
Compose config --quiet: passed
Env example TTL=7 and public origin=https://example.com: passed
Unset TTL defaults to 7; absent public origin stays empty: passed
Override TTL=3 and public origin=https://app.example:8443: passed
Empty TTL defaults to 7: passed
```

### Review, scope preservation, and concerns

The complete scoped diff was reviewed directly. Only the three production fixes, their focused tests, the two env examples, Compose, and this report are included in the fix commit. Unrelated development-progress documentation and planning files remain untouched. The required Copilot co-author trailer is included.

No outstanding implementation concern was identified. Container runtime behavior was not exercised because Docker is unavailable; Compose schema validation and actual interpolation were verified using the official standalone CLI. The temporary CLI and checksum download are not repository changes.
