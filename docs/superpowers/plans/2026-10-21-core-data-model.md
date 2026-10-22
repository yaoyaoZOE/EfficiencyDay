# Core Data Model and Minimal Auth/Work-Item API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the approved three-table business model and the first protected login/create/read work-item API chain without expanding into week-two editing or deferred child tables.

**Architecture:** Keep the existing FastAPI/SQLAlchemy/Alembic/SQLite modular monolith. Add explicit relational models and a reviewed Alembic migration, then add session-backed authentication and user-scoped work-item endpoints; application startup never runs migrations.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic Settings, SQLAlchemy 2.x, Alembic, SQLite, pytest, Ruff, Argon2id (`argon2-cffi`), Docker Compose, Nginx.

## Global Constraints

- The SQLite database remains a local persistent file with foreign keys enabled, WAL mode, `synchronous=FULL`, and a 5-second busy timeout.
- System timestamps are normalized to UTC; `due_on`, `started_on`, and `completed_on` are SQL `DATE` values interpreted in the user's IANA time zone.
- The default account time zone is `Asia/Shanghai`.
- Passwords use Argon2id; session cookies are `HttpOnly`, `Secure`, and `SameSite`.
- CSRF `Origin` validation compares against configured `EFFICIENCYDAY_PUBLIC_ORIGIN`; forwarded headers are not trusted as the source of the allowed origin.
- A session lasts 7 days by default and is configurable with `EFFICIENCYDAY_SESSION_TTL_DAYS`.
- Users, sessions, and work items are the only tables added in this plan. Checklist, note, template, annual-plan, and status-event tables are excluded.
- A work item with either priority field unset is unclassified; color is only a visual marker.
- Work-item reads and writes always filter by both current user and work-item ID.
- Work-item list endpoints are paginated with a default page size of 50 and a maximum page size of 100.
- Login and work-item writes must have explicit error responses; no exception is converted into a success-shaped response.
- Run tests against temporary databases. Do not run migration commands against `backend/data/efficiencyday.db`.
- The backend remains a single Uvicorn worker; do not introduce Redis, a task queue, or a second API instance.

---

## Repository File Map

| File | Responsibility in this plan |
| --- | --- |
| `backend/pyproject.toml` | Declare `argon2-cffi` as a runtime dependency. |
| `backend/requirements.lock` | Lock the added runtime dependency using the repository's existing `uv pip compile` workflow. |
| `backend/.env.example` | Document local-only first-account and session lifetime settings without including credential values. |
| `backend/app/core/config.py` | Parse optional initial credentials, positive session lifetime, and optional public origin. |
| `backend/app/core/time.py` | Provide UTC timestamp and account-local date helpers. |
| `backend/app/core/security.py` | Hash/verify passwords and create/hash opaque session and CSRF tokens. |
| `backend/app/db/types.py` | Normalize UTC timestamps through SQLite's timezone-naive storage. |
| `backend/app/db/models.py` | Define `User`, `SessionRecord`, and `WorkItem` and their constraints. |
| `backend/app/db/session.py` | Build a synchronous SQLAlchemy session factory and request-scoped DB dependency. |
| `backend/app/db/migrations.py` | Share current Alembic revision lookup between readiness and bootstrap. |
| `backend/migrations/versions/0002_core_domain.py` | Add the three core tables, checks, foreign keys, and indexes. |
| `backend/app/services/bootstrap.py` | Create the initial account once, only after migrations are current. |
| `backend/app/services/auth.py` | Authenticate users and create/revoke persisted sessions. |
| `backend/app/services/work_items.py` | Create and read work items with mandatory user scoping. |
| `backend/app/api/dependencies.py` | Resolve the current session/user and validate CSRF and request origin. |
| `backend/app/schemas/auth.py` | Define login and current-user response contracts. |
| `backend/app/schemas/work_items.py` | Define create/list/detail contracts. |
| `backend/app/api/auth.py` | Expose login, current-user, and logout routes. |
| `backend/app/api/work_items.py` | Expose user-scoped create/list/detail routes. |
| `backend/app/api/health.py` | Preserve current liveness/readiness response behavior while using shared migration lookup. |
| `backend/app/main.py` | Initialize engine/session factory, conditionally bootstrap, and register routers. |
| `backend/tests/conftest.py` | Share isolated Alembic migration helpers for tests. |
| `backend/tests/test_config.py` | Test auth configuration defaults and invalid lifetime values. |
| `backend/tests/test_time.py` | Test UTC and account-time-zone date conversion. |
| `backend/tests/test_models.py` | Test migration preservation, model constraints, and UTC timestamp behavior. |
| `backend/tests/test_bootstrap.py` | Test one-time initialization and migration-readiness gating. |
| `backend/tests/test_auth.py` | Test password, session, cookie, CSRF, expiry, and logout behavior. |
| `backend/tests/test_work_items.py` | Test creation, read scoping, classification, and date-only fields. |
| `backend/tests/test_health.py` | Retain existing health behavior and add auth/bootstrap startup cases. |
| `backend/Dockerfile` | Stop automatically migrating at container startup and launch Uvicorn without wildcard forwarded-header trust. |
| `docker-compose.yml` | Pass only configured bootstrap/session variables and keep the backend unexposed. |
| `.env.example` | Document Compose-time bootstrap/session/public-origin variables; actual `.env` remains ignored by Git. |
| `frontend/Dockerfile` | Copy the Nginx rate-limit zone configuration into the Nginx `http` include directory. |
| `frontend/nginx-rate-limit.conf` | Define the login request rate-limit zone. |
| `frontend/nginx.conf` | Apply the rate limit to the login endpoint and retain existing proxy behavior. |

## Task 1: Add Security Configuration and UTC Date Helpers

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/requirements.lock`
- Modify: `backend/app/core/config.py`
- Create: `backend/app/core/time.py`
- Modify: `backend/.env.example`
- Test: `backend/tests/test_config.py`
- Test: `backend/tests/test_time.py`

**Interfaces:**
- Produces `Settings.initial_username: str | None`, `Settings.initial_password: SecretStr | None`, and `Settings.session_ttl_days: PositiveInt`.
- Produces `utc_now() -> datetime` and `local_today(timezone_name: str, *, now: datetime | None = None) -> date`.
- A naive datetime passed to `local_today` raises `ValueError`; invalid IANA zone names are not silently replaced.

- [ ] **Step 1: Write settings and time tests**

Create `backend/tests/test_config.py`:

```python
import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_auth_settings_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.initial_username is None
    assert settings.initial_password is None
    assert settings.session_ttl_days == 7


def test_session_lifetime_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        Settings(session_ttl_days=0, _env_file=None)
```

Create `backend/tests/test_time.py`:

```python
from datetime import UTC, datetime, timedelta

import pytest

from app.core.time import local_today, utc_now


def test_utc_now_is_timezone_aware() -> None:
    assert utc_now().utcoffset() == timedelta(0)


def test_local_today_uses_account_timezone() -> None:
    instant = datetime(2026, 10, 21, 16, 30, tzinfo=UTC)

    assert local_today("Asia/Shanghai", now=instant).isoformat() == "2026-10-22"


def test_local_today_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        local_today("Asia/Shanghai", now=datetime(2026, 10, 21, 16, 30))
```

- [ ] **Step 2: Run the focused tests and confirm they fail because the new settings/helper are absent**

Run from the repository root:

```powershell
uv run --project backend --extra dev pytest backend/tests/test_config.py backend/tests/test_time.py -q
```

Expected: collection fails with missing `initial_username` / `app.core.time`; no unrelated test failure is acceptable.

- [ ] **Step 3: Add configuration, UTC helpers, dependency, and safe examples**

Add `argon2-cffi>=23.1,<27` to the runtime dependency list in `backend/pyproject.toml`. Extend `Settings` with:

```python
from pydantic import PositiveInt, SecretStr

initial_username: str | None = None
initial_password: SecretStr | None = None
session_ttl_days: PositiveInt = 7
```

Create `backend/app/core/time.py`:

```python
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo


def utc_now() -> datetime:
    return datetime.now(UTC)


def local_today(timezone_name: str, *, now: datetime | None = None) -> date:
    instant = now if now is not None else utc_now()
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    return instant.astimezone(ZoneInfo(timezone_name)).date()
```

Append comments and the non-secret default to `backend/.env.example`; do not put sample usernames or passwords in the file:

```dotenv
# Set both values only for the first startup with an empty, migrated database.
# EFFICIENCYDAY_INITIAL_USERNAME=
# EFFICIENCYDAY_INITIAL_PASSWORD=
EFFICIENCYDAY_SESSION_TTL_DAYS=7
```

- [ ] **Step 4: Run tests and refresh the checked-in lock file**

Run:

```powershell
uv run --project backend --extra dev pytest backend/tests/test_config.py backend/tests/test_time.py -q
uv pip compile backend\pyproject.toml --extra dev --output-file backend\requirements.lock
```

Expected: focused tests pass; the lock lists `argon2-cffi` and its resolved dependencies.

- [ ] **Step 5: Commit the independently tested configuration change**

```powershell
git add backend/pyproject.toml backend/requirements.lock backend/app/core/config.py backend/app/core/time.py backend/.env.example backend/tests/test_config.py backend/tests/test_time.py
git commit -m "feat: add auth configuration and UTC helpers" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

## Task 2: Add Core Models and the `0002` Alembic Migration

**Files:**
- Create: `backend/app/db/types.py`
- Modify: `backend/app/db/models.py`
- Create: `backend/migrations/versions/0002_core_domain.py`
- Create: `backend/tests/conftest.py`
- Modify: `backend/tests/test_health.py`
- Test: `backend/tests/test_models.py`

**Interfaces:**
- Produces mapped classes `User`, `SessionRecord`, and `WorkItem`, all inheriting the existing `Base`.
- `SessionRecord` stores `token_hash` and `csrf_token`; only the authentication token is hashed.
- `WorkItem.status` is one of `pending`, `in_progress`, `completed`, or `cancelled`; new items default to `pending`.
- `WorkItem.version` starts at 1. `completed_on` must be non-null exactly when status is `completed`.
- `UTCDateTime` accepts aware datetimes, stores UTC-normalized values, and returns aware UTC datetimes.

- [ ] **Step 1: Add a shared temporary-database migration helper**

Create `backend/tests/conftest.py` with `make_alembic_config(database_path: Path) -> Config` and `migrate_database(database_path: Path, revision: str = "head") -> None`. The helper must set `sqlalchemy.url` to the test path and call `command.upgrade`; it must not use the repository's default database. Update the existing `test_health.py` helper to call this shared function.

- [ ] **Step 2: Write failing migration and constraint tests**

Create tests that:

1. Upgrade a temporary database to `0001`, insert one `app_metadata` row, then upgrade to `head`; assert `app_metadata`, `users`, `sessions`, and `work_items` all exist and the metadata row remains.
2. Downgrade that test database to `0001`, verify only the three new tables are removed, and upgrade to `head` again.
3. Insert a valid user and work item, then verify SQLite rejects duplicate usernames, unknown statuses, non-positive versions, invalid color keys, and a completion date inconsistent with status.
4. Verify `sessions.user_id` and `work_items.user_id` foreign keys cascade on user deletion.
5. Round-trip an aware non-UTC timestamp through `UTCDateTime` and assert the loaded value is aware UTC with the same instant.

Run:

```powershell
uv run --project backend --extra dev pytest backend/tests/test_models.py -q
```

Expected: tests fail because the core models, migration, and shared helper do not yet exist.

- [ ] **Step 3: Implement UTC persistence and the SQLAlchemy models**

Create `backend/app/db/types.py` with a `TypeDecorator[datetime]` backed by `DateTime(timezone=False)`: reject naive bind values, convert aware values to UTC and strip `tzinfo` only for SQLite storage, then attach UTC to loaded naive values.

Extend `backend/app/db/models.py` with:

- `User`: integer primary key, unique non-null username, non-null password hash, `timezone` default `Asia/Shanghai`, and UTC `created_at`.
- `SessionRecord`: integer primary key, cascading user foreign key, unique non-null session-token hash, non-null random CSRF token, UTC created/expiry timestamps, nullable UTC revocation timestamp, and indexes on user and expiry.
- `WorkItem`: integer primary key, cascading user foreign key, required title, status default `pending`, nullable urgency/importance booleans, nullable color key, nullable SQL `Date` fields `due_on`, `started_on`, and `completed_on`, nullable text fields `background`, `goal`, `result`, and `reflection`, positive version defaulting to 1, and UTC created/updated timestamps.

Use explicit named checks for legal status, booleans in `{0,1}`, color keys in `{gray, blue, green, yellow, orange, red, purple}`, positive version, and `completed_on` consistency. Add `work_items(user_id)` and `work_items(user_id, status)` indexes. Keep `AppMetadata` unchanged.

- [ ] **Step 4: Implement the additive migration**

Create revision `0002` with `down_revision = "0001"`. Use `op.create_table` for `users`, `sessions`, and `work_items`, then add the indexes and checks from Step 3. Use SQL `DATE` for the three calendar-date fields and SQL `DATETIME` for UTC-normalized timestamps. In `downgrade()`, drop indexes and tables in foreign-key-safe order (`work_items`, `sessions`, then `users`); never drop `app_metadata`.

- [ ] **Step 5: Run the migration/model test and existing health tests**

Run:

```powershell
uv run --project backend --extra dev pytest backend/tests/test_models.py backend/tests/test_health.py -q
```

Expected: all migration, model-constraint, health, and `0001` preservation tests pass.

- [ ] **Step 6: Commit the migration and models**

```powershell
git add backend/app/db/types.py backend/app/db/models.py backend/migrations/versions/0002_core_domain.py backend/tests/conftest.py backend/tests/test_health.py backend/tests/test_models.py
git commit -m "feat: add core business data models" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

## Task 3: Add Request Sessions and One-Time Account Bootstrap

**Files:**
- Modify: `backend/app/db/session.py`
- Create: `backend/app/db/migrations.py`
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/bootstrap.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/api/health.py`
- Test: `backend/tests/test_bootstrap.py`
- Test: `backend/tests/test_health.py`

**Interfaces:**
- Produces `create_session_factory(engine) -> sessionmaker[Session]` and a request-scoped `get_db(request) -> Generator[Session]`.
- Produces `get_current_revision(engine) -> str | None` and `get_expected_revision() -> str`.
- Produces `ensure_initial_user(session_factory, settings) -> None`; it creates one user only when the migrated user table is empty.

- [ ] **Step 1: Write bootstrap and health regression tests**

Test the following cases using a temporary path and the shared migration helper:

- A migrated empty database plus both valid bootstrap settings creates exactly one user.
- A second bootstrap call does not change that user's password hash.
- A migrated empty database with missing or blank credentials raises a clear `RuntimeError`.
- An existing user allows startup without bootstrap credentials.
- The migrated healthy-readiness test supplies valid bootstrap credentials or seeds a user before starting the application.
- An un-migrated database does not attempt user initialization; `/health/live` remains 200 and `/health/ready` remains 503.
- An unavailable database does not prevent the liveness endpoint from responding; readiness returns its existing 503 response.

Run:

```powershell
uv run --project backend --extra dev pytest backend/tests/test_bootstrap.py backend/tests/test_health.py -q
```

Expected: tests fail because session factories and bootstrap handling do not exist.

- [ ] **Step 2: Add session factory and shared migration revision lookup**

In `backend/app/db/session.py`, create a synchronous `sessionmaker` with `expire_on_commit=False`; implement `get_db` as a generator that opens one `Session` from `request.app.state.session_factory` and closes it after the request.

In `backend/app/db/migrations.py`, derive the expected head from `ScriptDirectory.from_config(Config(...))` and the current revision from `MigrationContext.configure(connection).get_current_revision()`. Let SQLAlchemy errors propagate to the caller; do not turn unavailable databases into an up-to-date result.

- [ ] **Step 3: Implement one-time initial account creation**

In `backend/app/services/bootstrap.py`, query for an existing `User` in one transaction. If one exists, return without reading or applying new credentials. If none exists, require non-blank username and `SecretStr` password, hash the password with `PasswordHasher` from `argon2-cffi`, and insert the user with timezone `Asia/Shanghai`. Raise `RuntimeError` on missing/blank credentials; do not log credential values.

- [ ] **Step 4: Gate bootstrap on the migration revision without changing health semantics**

In the lifespan in `main.py`, create and publish both engine and session factory. Compare current and expected revisions before calling bootstrap. Skip bootstrap when revisions differ. Catch only `SQLAlchemyError` around the startup readiness probe, log the exception, and continue to lifespan yield so liveness can respond; do not catch bootstrap validation errors. Dispose the engine on lifespan exit.

Refactor `health.py` to use `get_current_revision` and `get_expected_revision` while preserving exact response bodies and status codes for live, unavailable database, and stale migration cases.

- [ ] **Step 5: Run bootstrap and health tests**

Run:

```powershell
uv run --project backend --extra dev pytest backend/tests/test_bootstrap.py backend/tests/test_health.py -q
```

Expected: all bootstrap cases pass and existing health response contracts remain unchanged.

- [ ] **Step 6: Commit request-session and bootstrap changes**

```powershell
git add backend/app/db/session.py backend/app/db/migrations.py backend/app/services/__init__.py backend/app/services/bootstrap.py backend/app/main.py backend/app/api/health.py backend/tests/test_bootstrap.py backend/tests/test_health.py
git commit -m "feat: bootstrap the initial user after migration" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

## Task 4: Implement Session-Backed Authentication and CSRF Checks

**Files:**
- Modify: `backend/app/core/config.py`
- Create: `backend/app/core/security.py`
- Create: `backend/app/schemas/__init__.py`
- Create: `backend/app/schemas/auth.py`
- Create: `backend/app/api/dependencies.py`
- Create: `backend/app/services/auth.py`
- Create: `backend/app/api/auth.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_config.py`
- Modify: `backend/.env.example`
- Modify: `docker-compose.yml`
- Create: `.env.example`
- Test: `backend/tests/test_auth.py`

**Interfaces:**
- Pure security helpers: `hash_password(password: str) -> str`, `verify_password(password: str, encoded: str) -> bool`, `create_opaque_token() -> str`, and `hash_token(token: str) -> str`.
- Auth service: `authenticate_user(session, username, password) -> tuple[User, SessionRecord, str] | None`, `revoke_session(session, session_record, now) -> None`.
- Auth API: `POST /api/v1/auth/login`, `GET /api/v1/auth/me`, `POST /api/v1/auth/logout`.
- Request dependencies: `get_current_session(request, db) -> SessionRecord`, `get_current_user(...) -> User`, and `require_csrf(request, current_session) -> None`.
- `Settings.public_origin: AnyHttpUrl | None`; unsafe requests fail with `503` if it is absent.
- Unknown usernames still run one Argon2id verification against a fixed dummy hash before returning the generic authentication failure.

- [ ] **Step 1: Write failing authentication tests**

Use `TestClient(create_app(settings), base_url="https://testserver")` so the secure session cookie is exercised. Set `Settings.public_origin` explicitly in auth tests. Test:

- Password hashing does not return the plaintext and verifies correct/incorrect passwords.
- Valid login returns a generic success response, sets an `HttpOnly`, `Secure`, `SameSite` session cookie, and persists only the hash of the session token.
- Invalid username and invalid password both return the same `401` detail.
- Unknown usernames perform the same Argon2id verification operation as a wrong password for a known username.
- `/auth/me` returns the authenticated user, timezone, and session CSRF token.
- Missing public-origin configuration returns `503` for unsafe requests. A configured public origin accepts only an exact scheme/host/port match; an internal HTTP request carrying the configured external HTTPS Origin succeeds without trusting forwarded headers.
- Missing or mismatched CSRF header and an invalid `Origin` are rejected for logout and other unsafe authenticated routes.
- Logout sets `revoked_at`, clears the cookie, and makes the previous session unusable.
- Expired and revoked sessions cannot authenticate.

Run:

```powershell
uv run --project backend --extra dev pytest backend/tests/test_auth.py -q
```

Expected: tests fail because auth schemas, services, and routes are absent.

- [ ] **Step 2: Implement password and opaque-token helpers**

Use `argon2.PasswordHasher()` with its Argon2id defaults. Keep one valid fixed dummy Argon2id hash generated with the same parameters. Catch only Argon2's mismatch and invalid-hash exceptions in `verify_password` and return `False` for those cases. Generate tokens with `secrets.token_urlsafe(32)` and store `hashlib.sha256(token.encode("utf-8")).hexdigest()`; never log either raw token.

- [ ] **Step 3: Implement authentication/session service**

Query usernames exactly as stored. Select the stored password hash for a known user or the fixed dummy hash for an unknown user, then always call `verify_password` before deciding whether to return `None`; this keeps the expensive Argon2 work on both credential-failure paths. On success create a random session token and a separate random CSRF token, persist the session-token hash and CSRF token with UTC `created_at` and `expires_at = utc_now() + timedelta(days=settings.session_ttl_days)`, and return the raw session token only to the route for the cookie. Return `None` for either unknown username or bad password.

When loading a session, require matching token hash, `revoked_at IS NULL`, and `expires_at > utc_now()`. Logout sets `revoked_at` in the same transaction.

- [ ] **Step 4: Implement authentication dependencies and routes**

Add optional `Settings.public_origin: AnyHttpUrl | None` and validate it as an origin without userinfo, a path, query, or fragment. Treat an empty environment value as absent. Login and all unsafe requests require it; when absent, return `503` with an explicit configuration error. Parse `Origin` and compare its normalized scheme, host, and port to the configured origin. Do not derive the allowed origin from forwarded headers. Map `EFFICIENCYDAY_PUBLIC_ORIGIN` and `EFFICIENCYDAY_SESSION_TTL_DAYS` through the backend service in `docker-compose.yml`, and document both in the env examples. Login sets a cookie named `efficiencyday_session` with `httponly=True`, `secure=True`, `samesite="lax"`, and `path="/"`. `/auth/me` returns the raw CSRF token associated with the authenticated session. On authenticated unsafe requests compare `X-CSRF-Token` to the stored value with `hmac.compare_digest`. Do not expose password hashes, session hashes, or CSRF tokens in logs.

Logout requires a valid session and CSRF check, revokes the record, and clears `efficiencyday_session` with the same cookie attributes.

- [ ] **Step 5: Register the auth router and run the focused suite**

Include the auth router under `/api/v1`. Run:

```powershell
uv run --project backend --extra dev pytest backend/tests/test_auth.py backend/tests/test_bootstrap.py backend/tests/test_health.py -q
```

Expected: auth, bootstrap, liveness, and readiness tests pass.

- [ ] **Step 6: Commit authentication**

```powershell
git add backend/app/core/config.py backend/app/core/security.py backend/app/schemas/__init__.py backend/app/schemas/auth.py backend/app/api/dependencies.py backend/app/services/auth.py backend/app/api/auth.py backend/app/main.py backend/tests/test_config.py backend/.env.example docker-compose.yml .env.example backend/tests/test_auth.py
git commit -m "feat: add revocable cookie sessions" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

## Task 5: Implement User-Scoped Work-Item Create and Read

**Files:**
- Create: `backend/app/schemas/work_items.py`
- Create: `backend/app/services/work_items.py`
- Create: `backend/app/api/work_items.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_work_items.py`

**Interfaces:**
- `WorkItemCreate`: title, optional nullable priority flags, optional color key, optional target date, and optional detail text; the service always sets status to `pending`.
- `create_work_item(session, user, payload) -> WorkItem`.
- `get_work_item(session, user_id, work_item_id) -> WorkItem | None`.
- `list_work_items(session, user_id, *, limit: int, offset: int) -> list[WorkItem]`.
- `WorkItemStatus = Literal["pending", "in_progress", "completed", "cancelled"]`.
- `apply_status_transition(item: WorkItem, target_status: WorkItemStatus, timezone_name: str, *, now: datetime | None = None) -> None`; validates the approved transition graph and updates local calendar dates, but is not exposed as an HTTP edit route in this week-one plan.
- Routes: `POST /api/v1/work-items`, paginated `GET /api/v1/work-items`, and `GET /api/v1/work-items/{id}`.

- [ ] **Step 1: Write failing API tests**

Create tests that:

- An authenticated user can create a task with only a title; the saved status is `pending`, version is 1, priority fields remain `NULL`, and `completed_on` is `NULL`.
- An authenticated user can create an explicitly classified task with a `due_on` SQL `DATE` value and read it back without time conversion.
- `/work-items` lists only tasks belonging to the authenticated user.
- A user cannot read another user's work item by ID; both a nonexistent ID and another user's ID return the same `404` response.
- List pagination defaults to 50 items, caps `limit` at 100, rejects non-positive limits and negative offsets, and orders equal timestamps by descending ID.
- Missing authentication returns `401`; invalid request fields return `422`; a write without a valid CSRF token/origin is rejected.
- A task with one or both priority fields unset is represented as unclassified; no urgency or importance is inferred from `due_on` or color.
- Unit tests cover every allowed and rejected status transition, direct completion, reopening, first-start date assignment, date preservation after returning to pending, and the Shanghai date boundary.

Run:

```powershell
uv run --project backend --extra dev pytest backend/tests/test_work_items.py -q
```

Expected: collection or route assertions fail because the schemas, service, and router are absent.

- [ ] **Step 2: Implement request and response schemas**

Create explicit Pydantic models for create, detail, and paginated list output. The create request does not accept `status`, `started_on`, or `completed_on`; the service always creates a `pending` work item, and lifecycle dates are written by the transition service. Accept `due_on` as `date | None`; retain nullable priority values; expose `version` and the approved text detail fields; never expose `user_id` as a client-controlled create field. Use `limit: int = 50` constrained to 1–100 and `offset: int = 0` constrained to non-negative values.

- [ ] **Step 3: Implement user-scoped service queries**

Implement creation with `user_id` supplied only from the authenticated dependency and status set to `pending`. Implement list and detail queries with `WorkItem.user_id == current_user.id`. Order the initial list deterministically by `created_at DESC, id DESC`. Implement `apply_status_transition` with the graph in the design spec: entering `in_progress` sets `started_on` only if it is empty; entering `completed` sets `completed_on` to the account-local date; leaving `completed` clears `completed_on`; returning to `pending` preserves `started_on`. The helper raises `ValueError` for an edge not in the graph and does not persist or increment `version`. Commit create/read operations within the request transaction and allow database exceptions to reach the standard error handler.

- [ ] **Step 4: Implement routes and register the router**

Use the shared `get_db`, current-user dependency, and CSRF dependency on `POST`. Return `201` for create, `200` for reads, and `404` for either missing or non-owned IDs. Register the router under `/api/v1`.

- [ ] **Step 5: Run focused API and regression tests**

Run:

```powershell
uv run --project backend --extra dev pytest backend/tests/test_work_items.py backend/tests/test_auth.py backend/tests/test_health.py -q
```

Expected: all task ownership, auth, error-contract, and health tests pass.

- [ ] **Step 6: Commit the work-item API**

```powershell
git add backend/app/schemas/work_items.py backend/app/services/work_items.py backend/app/api/work_items.py backend/app/main.py backend/tests/test_work_items.py
git commit -m "feat: add protected work item create and read API" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

## Task 6: Make Deployment Migration Explicit and Wire Safe Runtime Settings

**Files:**
- Modify: `backend/Dockerfile`
- Modify: `docker-compose.yml`
- Modify: `.env.example`
- Modify: `frontend/Dockerfile`
- Create: `frontend/nginx-rate-limit.conf`
- Modify: `frontend/nginx.conf`

**Interfaces:**
- `docker compose run --rm backend python -m alembic upgrade head` is the explicit migration command.
- The backend container starts Uvicorn without running Alembic.
- Compose passes bootstrap credentials, session TTL, and `EFFICIENCYDAY_PUBLIC_ORIGIN` into the private backend service but never publishes the backend port.
- Nginx limits login requests to five per minute per remote IP and returns HTTP `429` when limited.

- [ ] **Step 1: Record the current deployment behavior and validate the existing Compose file**

Run:

```powershell
Select-String -Path backend\Dockerfile -Pattern "alembic upgrade head"
docker compose config -q
```

Expected: the first command finds the current automatic migration command; the second validates the unmodified Compose configuration. After Step 2 the first command must return no match.

- [ ] **Step 2: Stop automatic migration and keep explicit deployment order**

Change `backend/Dockerfile` to start the API directly:

```dockerfile
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "6931"]
```

Keep migrations as an explicit operator step, using the same image and Compose database volume:

```powershell
docker compose run --rm backend python -m alembic upgrade head
docker compose up -d
```

Do not execute this command against a developer's real database during tests.

- [ ] **Step 3: Wire runtime configuration without committing secrets**

Map the following variables in the backend service's `environment` block:

```yaml
EFFICIENCYDAY_INITIAL_USERNAME: ${EFFICIENCYDAY_INITIAL_USERNAME:-}
EFFICIENCYDAY_INITIAL_PASSWORD: ${EFFICIENCYDAY_INITIAL_PASSWORD:-}
EFFICIENCYDAY_SESSION_TTL_DAYS: ${EFFICIENCYDAY_SESSION_TTL_DAYS:-7}
EFFICIENCYDAY_PUBLIC_ORIGIN: ${EFFICIENCYDAY_PUBLIC_ORIGIN:-}
```

Update root `.env.example` with explanatory comments, a 7-day TTL, the public-origin setting added in Task 4, and commented empty bootstrap variable names. Document that browser writes fail closed until the public origin is set. Keep `.env` ignored by `.gitignore`; do not add a username or password value. Leave the backend without a host-published port. Do not enable wildcard trusted-proxy forwarding flags.

- [ ] **Step 4: Apply login throttling at the existing Nginx edge**

Create `frontend/nginx-rate-limit.conf`:

```nginx
limit_req_zone $binary_remote_addr zone=login:10m rate=5r/m;
```

Copy it from `frontend/Dockerfile` into `/etc/nginx/conf.d/00-rate-limit.conf`, which Nginx includes inside its `http` context. In `frontend/nginx.conf`, add an exact `/api/v1/auth/login` location before the generic `/api/` location; use the same backend proxy headers/timeouts as the existing API location and apply `limit_req zone=login burst=4 nodelay` plus `limit_req_status 429`. The limit key must use `$binary_remote_addr`, not a client-controlled header. The four-request burst allows five immediate requests total; the sixth should receive 429.

- [ ] **Step 5: Validate the full backend, Nginx, and Compose configuration**

Run:

```powershell
uv run --project backend --extra dev pytest backend/tests -q
uv run --project backend --extra dev ruff check backend/app backend/tests backend/migrations
docker compose config -q
docker compose build backend frontend
docker compose run --rm --no-deps frontend nginx -t
```

Expected: all tests and Ruff pass, Compose configuration is valid, both images build, and Nginx syntax validation succeeds. Inspect the backend Docker CMD and confirm migration is not run at application startup; do not deploy to a server in this task.

For an isolated local rate-limit check, use a unique Compose project and port; do not reuse a real deployment volume:

```powershell
$previousUsername = $null
$previousPassword = $null
$previousPort = $null
$previousOrigin = $null
if (Test-Path Env:EFFICIENCYDAY_INITIAL_USERNAME) { $previousUsername = $env:EFFICIENCYDAY_INITIAL_USERNAME }
if (Test-Path Env:EFFICIENCYDAY_INITIAL_PASSWORD) { $previousPassword = $env:EFFICIENCYDAY_INITIAL_PASSWORD }
if (Test-Path Env:EFFICIENCYDAY_PORT) { $previousPort = $env:EFFICIENCYDAY_PORT }
if (Test-Path Env:EFFICIENCYDAY_PUBLIC_ORIGIN) { $previousOrigin = $env:EFFICIENCYDAY_PUBLIC_ORIGIN }
$env:EFFICIENCYDAY_INITIAL_USERNAME = "rate-test"
$env:EFFICIENCYDAY_INITIAL_PASSWORD = "temporary-test-only"
$env:EFFICIENCYDAY_PORT = "18327"
$env:EFFICIENCYDAY_PUBLIC_ORIGIN = "http://127.0.0.1:18327"
try {
    docker compose -p ed-rate-check run --rm backend python -m alembic upgrade head
    docker compose -p ed-rate-check up -d --build
    Start-Sleep -Seconds 10
    $codes = 1..6 | ForEach-Object {
        curl.exe -s -o NUL -w "%{http_code}`n" -H "Content-Type: application/json" -H "Origin: http://127.0.0.1:18327" -d '{"username":"wrong","password":"wrong"}' http://127.0.0.1:18327/api/v1/auth/login
    }
    $codes
    if ($codes[-1] -ne "429") { throw "The sixth login request did not return HTTP 429." }
}
finally {
    docker compose -p ed-rate-check down --volumes
    if ($null -eq $previousUsername) { Remove-Item Env:EFFICIENCYDAY_INITIAL_USERNAME } else { $env:EFFICIENCYDAY_INITIAL_USERNAME = $previousUsername }
    if ($null -eq $previousPassword) { Remove-Item Env:EFFICIENCYDAY_INITIAL_PASSWORD } else { $env:EFFICIENCYDAY_INITIAL_PASSWORD = $previousPassword }
    if ($null -eq $previousPort) { Remove-Item Env:EFFICIENCYDAY_PORT } else { $env:EFFICIENCYDAY_PORT = $previousPort }
    if ($null -eq $previousOrigin) { Remove-Item Env:EFFICIENCYDAY_PUBLIC_ORIGIN } else { $env:EFFICIENCYDAY_PUBLIC_ORIGIN = $previousOrigin }
}
```

Expected: the final status code is `429`; the first five requests are not rate-limited. The isolated Compose volume is removed in `finally`.

- [ ] **Step 6: Commit deployment wiring**

```powershell
git add backend/Dockerfile docker-compose.yml backend/.env.example .env.example frontend/Dockerfile frontend/nginx-rate-limit.conf frontend/nginx.conf
git commit -m "chore: make database migration explicit" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

## Final Acceptance Checklist

- [ ] `0002` upgrades from `0001`, preserves `app_metadata`, and passes isolated upgrade/downgrade/re-upgrade tests.
- [ ] Initial account is created once only after the schema reaches the Alembic head; absent credentials fail explicitly.
- [ ] Existing health liveness/readiness contracts pass unchanged.
- [ ] Login, CSRF validation, logout revocation, session expiry, and generic credential errors pass.
- [ ] Authenticated users can create and read their own work items; another user's records are indistinguishable from missing records.
- [ ] Unit tests cover the approved status/date transition rules without exposing a week-two edit route.
- [ ] Work-item list responses honor the 50-item default, 100-item maximum, and stable ordering.
- [ ] SQL `DATE` fields remain date-only and nullable priority values remain unclassified.
- [ ] Compose keeps the backend private, forwards no committed secret, and Nginx login throttling returns `429`.
- [ ] Full backend tests, Ruff, Compose validation, and both image builds pass before marking the work complete.

## Deliberately Deferred

- Work-item update/status-transition API and version-conflict `409` behavior; implement with the week-two editing work.
- Execution checklist, process-note, template, annual-plan, and status-event tables.
- Frontend login/task screens, password recovery, registration, offline editing, and real-time push.
- Server deployment, domain/HTTPS/public-network verification, and backup/restore drills.
