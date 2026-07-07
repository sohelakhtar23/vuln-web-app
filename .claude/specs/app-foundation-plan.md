# Implementation Plan: Vulnerable Web Application

**Project:** Vulnerable Web Application — Security Lab
**Document type:** Step-by-step implementation plan
**Companion documents:** `docs/PRD.md`, `docs/TDD.md`, `.claude/specs/app-foundation.md`
**Audience:** Engineer executing the build

---

## ⚠ Read Before Starting

This plan describes an **intentionally vulnerable** application. The 8 flaws catalogued in PRD §3.2 are **required features, not bugs** — they are the pedagogical payload. Every phase below calls out which vulnerabilities the code introduces and how to keep them in place:

- **VULN-1 (SQLi):** all SQL must be built with string concatenation. **Do not** use parameterized queries (`?` placeholders) or an ORM. The `INSERT` in `auth_service.signup`, the `SELECT` in `auth_service.login`, and the `LIKE` query in `auth.search` must all concatenate user input into the SQL string.
- **VULN-2 (Stored XSS):** the dashboard username injection must be a raw `str.replace('{{username}}', ...)`, **not** Jinja2 autoescape or `html.escape`.
- **VULN-3 (Reflected XSS):** the `/search` `q` parameter must be interpolated into the HTML response without escaping.
- **VULN-4 (Session Hijacking):** the session secret must be the hardcoded literal string `"super-secret-key-12345"`. **Do not** load it from env, generate it randomly, or use a stronger value.
- **VULN-5 (Weak Password Storage):** use `hashlib.md5(...).hexdigest()` with no salt and no pepper.
- **VULN-6 (Exposed DB):** the `/download/db` endpoint must not check `user_id` in the session.
- **VULN-7 (No Rate Limiting):** no rate-limiting middleware on any endpoint.
- **VULN-8 (CSRF):** no CSRF tokens on any form.

Any code review during execution that suggests "fixing" one of these is to be deferred. The vulnerabilities are the deliverable.

---

## ⚠ Spec/Implementation Reality Note

The PRD, TDD, and the original prompt for this plan all describe a `backend/pyproject.toml` (hatchling build, `pytest` dev dep) under `backend/`. However, the repository was scaffolded with `uv init .` at the project root, and the runtime dependencies (`fastapi`, `uvicorn`, `itsdangerous`, `python-multipart`) are already declared in the **root** `pyproject.toml`. There is no `backend/` directory yet.

**Resolution adopted by this plan:** skip creating `backend/pyproject.toml`. The root `pyproject.toml` already owns the runtime dependencies and `uv.lock` pins the resolved versions. `pytest` is **not** added (the project has no tests today; the plan can be executed and verified manually using the steps in Phase 10). If the user later wants a `backend/`-scoped project, that is a refactor — not part of this plan.

---

## Phase 1 — Project Structure

**Goal:** create the directory skeleton the rest of the plan writes into.

**Files and directories to create:**

```
backend/
├── app/
│   ├── __init__.py              (empty)
│   ├── main.py                  (Phase 6)
│   ├── core/
│   │   ├── __init__.py          (empty)
│   │   └── security.py          (Phase 3)
│   ├── db/
│   │   ├── __init__.py          (empty)
│   │   └── session.py           (Phase 2)
│   ├── services/
│   │   ├── __init__.py          (empty)
│   │   └── auth_service.py      (Phase 4)
│   └── api/
│       ├── __init__.py          (empty)
│       └── routes/
│           ├── __init__.py      (empty)
│           └── auth.py          (Phase 5)
frontend/
├── templates/                   (Phase 7)
│   ├── login.html
│   ├── signup.html
│   └── dashboard.html
└── static/
    ├── css/                     (Phase 8)
    │   └── styles.css
    └── images/                  (already exists with logos)
```

**Notes:**
- `backend/app/` will be a regular package (because of `__init__.py` files). Phase 6 sets up `sys.path` so the `app` package resolves regardless of the launch directory.
- `frontend/static/images/` is already populated with the three logo files (PUCIT, blue-logo-scl2, excaliat).
- **No new `pyproject.toml` is created** (see the spec/impl reality note above).

---

## Phase 2 — Database Layer

**File to create:** `backend/app/db/session.py`

**Responsibilities:**
- Open a SQLite connection to `vulnerable_app.db` at the **project root** (one level up from `backend/app/db/`).
- Set `check_same_thread=False` on the connection (simplifies FastAPI's threadpool use).
- Set `row_factory = sqlite3.Row` so callers can access columns by name.
- Provide `get_db() -> sqlite3.Connection` (a context-managed connection helper or a simple function — both are acceptable; pick one and document it).
- Provide `init_db() -> None` that runs `CREATE TABLE IF NOT EXISTS users (...)`.

**Schema (vulnerability-bearing):**
```sql
CREATE TABLE IF NOT EXISTS users (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    email    TEXT,
    password TEXT
)
```

The `UNIQUE` constraint on `username` is the **primary** mechanism preventing duplicate accounts (per business rule #6 in `app-foundation.md` §13). Do not duplicate the check in application code.

**Path note:** the DB file is at the project root, not inside `backend/`. Compute the path as `Path(__file__).resolve().parents[3] / "vulnerable_app.db"` (4 levels up from `db/session.py`: `db/`, `app/`, `backend/`, project root) — or use an env var, but the default must be the project-root file.

---

## Phase 3 — Security Utilities

**File to create:** `backend/app/core/security.py`

**Implementation:**
```python
import hashlib

def hash_password(password: str) -> str:
    # VULN-5: MD5 with no salt. INTENTIONAL — do not "fix".
    return hashlib.md5(password.encode("utf-8")).hexdigest()

def verify_password(plain: str, hashed: str) -> bool:
    return hash_password(plain) == hashed
```

**Hard rules:**
- Use `hashlib.md5`, **not** `hashlib.sha256`, `bcrypt`, `argon2`, or `passlib`.
- Do **not** concatenate, prepend, or append a salt to the password before hashing.
- Do **not** use `hmac` or a key derivation function.
- Both functions belong in the `core.security` module; no other module should import `hashlib` directly.

---

## Phase 4 — Business Logic (`auth_service.py`)

**File to create:** `backend/app/services/auth_service.py`

### 4.1 `signup(...)` function

**Signature:**
```python
def signup(username: str, email: str, password: str) -> Response
```
(`username`, `email`, `password` are FastAPI `Form()` params from the route — see Phase 5.)

**Logic:**
1. Validate that `username`, `email`, and `password` are all truthy. If any is missing/empty, return an `HTMLResponse` containing the error string `"All fields are required"` (or similar).
2. Call `hash_password(password)` to get the MD5 hexdigest.
3. **VULN-1: build the INSERT via string concatenation**:
   ```python
   query = (
       "INSERT INTO users (username, email, password) "
       "VALUES ('" + username + "', '" + email + "', '" + hashed + "')"
   )
   ```
   Do not use `?` placeholders. Do not use an ORM. The concatenation is the vulnerability.
4. Execute the query via a connection obtained from `db.session.get_db()`.
5. On success, return `RedirectResponse(url="/login", status_code=302)`.
6. On `sqlite3.IntegrityError` (the `UNIQUE` violation), return an `HTMLResponse` containing the string `"Username already exists"`.

**Suggested inline comment near the SQL:**
```python
# VULN-1: SQL Injection via string concatenation. INTENTIONAL.
```

### 4.2 `login(...)` function

**Signature:**
```python
def login(request: Request, username: str, password: str) -> Response
```

**Logic:**
1. Validate that `username` and `password` are truthy. If missing, return `JSONResponse({"success": False, "error": "Invalid credentials"}, status_code=401)`.
2. Call `hash_password(password)`.
3. **VULN-1: build the SELECT via string concatenation**:
   ```python
   query = (
       "SELECT * FROM users WHERE username = '" + username +
       "' AND password = '" + hashed + "'"
   )
   ```
4. Execute the query, fetch one row.
5. **If a row is returned (login success):**
   - Set `request.session["user_id"] = row["id"]`
   - Set `request.session["username"] = row["username"]`
   - Set `request.session["email"] = row["email"]`
   - Return `JSONResponse({"success": True, "redirect": "/welcome"}, status_code=200)`. **Not** a `RedirectResponse` — the frontend JS handles the redirect.
6. **If no row (login failure):**
   - Return `JSONResponse({"success": False, "error": "Invalid credentials"}, status_code=401)`.

**Critical contract:**
- Login **must** return `JSONResponse`, not `RedirectResponse`. The login form uses `fetch()` and reads `data.success` / `data.redirect` / `data.error`. A `RedirectResponse` here would break the inline error display and the no-page-reload UX.
- Signup **must** return `RedirectResponse` (HTTP 302). The signup form is a standard form submit, not a `fetch`.

---

## Phase 5 — Route Handlers (`auth.py`)

**File to create:** `backend/app/api/routes/auth.py`

**Setup:** all routes attach to a single `APIRouter`. Import `auth_service` from `app.services.auth_service` (resolves via the `sys.path` manipulation in `main.py`).

### 5.1 Route inventory

| Method | Path | Handler | Notes |
|--------|------|---------|-------|
| GET | `/` | `index()` | `RedirectResponse(url="/signup", status_code=302)` |
| GET | `/signup` | `signup_page()` | Read `frontend/templates/signup.html` from disk → `HTMLResponse` |
| POST | `/signup` | `signup_post(...)` | Forwards to `auth_service.signup(...)` |
| GET | `/login` | `login_page()` | Read `frontend/templates/login.html` from disk → `HTMLResponse` |
| POST | `/login` | `login_post(...)` | Forwards to `auth_service.login(request, ...)` |
| GET | `/download/db` | `download_db()` | **VULN-6:** no auth check. `FileResponse("vulnerable_app.db")` |
| GET | `/search` | `search_user(q: str = "")` | **VULN-3:** string concat in SQL **and** HTML |
| GET | `/welcome` | `welcome_page(request)` | Auth check + read template + `str.replace` |
| GET | `/logout` | `logout(request)` | `request.session.clear()` + redirect to `/login` |

### 5.2 Template reading convention

For `signup_page` and `login_page`:
```python
TEMPLATES_DIR = Path(__file__).resolve().parents[4] / "frontend" / "templates"

def signup_page():
    html = (TEMPLATES_DIR / "signup.html").read_text(encoding="utf-8")
    return HTMLResponse(html)
```
(4 levels up: `routes/`, `api/`, `app/`, `backend/` — then `frontend/templates/`.)

For `welcome_page`:
```python
def welcome_page(request: Request):
    if "user_id" not in request.session:
        return RedirectResponse(url="/login", status_code=302)
    html = (TEMPLATES_DIR / "dashboard.html").read_text(encoding="utf-8")
    # VULN-2: Stored XSS — no html.escape. INTENTIONAL.
    html = html.replace("{{username}}", request.session["username"])
    return HTMLResponse(html)
```

### 5.3 `/download/db` — VULN-6

```python
def download_db():
    db_path = Path(__file__).resolve().parents[4] / "vulnerable_app.db"
    # VULN-6: Exposed Database — no auth check. INTENTIONAL.
    return FileResponse(db_path, filename="vulnerable_app.db")
```
Do **not** add a session check. Do **not** add a CSRF check.

### 5.4 `/search` — VULN-3

```python
def search_user(q: str = ""):
    if not q:
        return HTMLResponse("Error: query parameter 'q' is required", status_code=400)
    try:
        conn = get_db()
        # VULN-1 + VULN-3: SQL injection via string concat.
        # VULN-3:     Reflected XSS — q is interpolated into the HTML response below.
        query = (
            "SELECT username, email FROM users "
            "WHERE username LIKE '%" + q + "%' OR email LIKE '%" + q + "%'"
        )
        rows = conn.execute(query).fetchall()
        items = "".join(
            f"<li>{row['username']} ({row['email']})</li>"  # VULN-3: no escaping
            for row in rows
        )
        return HTMLResponse(f"<h1>Search results for: {q}</h1><ul>{items}</ul>")
    except Exception as e:
        # Information disclosure: raw exception returned in body.
        return HTMLResponse(f"Error: {str(e)}", status_code=500)
```

**Do not:**
- Use parameterized queries.
- HTML-escape `q` before putting it in the response.
- HTML-escape `row['username']` or `row['email']` before putting them in `<li>`.

### 5.5 `/logout`

```python
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)
```

---

## Phase 6 — Application Entry Point (`main.py`)

**File to create:** `backend/app/main.py`

### 6.1 `sys.path` bootstrap (critical)

The very first executable lines of `main.py` must manipulate `sys.path` so that the `app` package imports resolve from **any** launch directory:

```python
import sys
from pathlib import Path

# Allow `python app/main.py` (from backend/) and
# `uv run backend/app/main.py` (from project root) to both work.
_BACKEND_DIR = Path(__file__).resolve().parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))
```

This must come **before** any `from app...` import. Without it, `uv run backend/app/main.py` from the project root fails because `app` is not on `sys.path`.

### 6.2 App construction

```python
import os
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles
import uvicorn

from app.api.routes.auth import router as auth_router
from app.db.session import init_db

app = FastAPI()

# VULN-4: Session Hijacking — hardcoded weak secret. INTENTIONAL.
app.add_middleware(
    SessionMiddleware,
    secret_key="super-secret-key-12345",
)

# Static asset mounts (CSS and images).
_PROJECT_ROOT = _BACKEND_DIR.parent
app.mount(
    "/static/css",
    StaticFiles(directory=_PROJECT_ROOT / "frontend" / "static" / "css"),
    name="static-css",
)
app.mount(
    "/static/images",
    StaticFiles(directory=_PROJECT_ROOT / "frontend" / "static" / "images"),
    name="static-images",
)

app.include_router(auth_router)

# Initialize DB on import.
init_db()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "3001"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)
```

**Decisions to honor:**
- The `PORT` env var defaults to `"3001"` if unset. Port is parsed via `int(...)` and bound to `0.0.0.0` (not `127.0.0.1`) so the app is reachable from other machines on the LAN — typical for classroom use.
- `reload=False` keeps behavior stable; auto-reload would re-run `init_db()` on every code change but is otherwise harmless. Either is fine; pick one and document.
- `uvicorn.run("app.main:app", ...)` uses the import string so workers can reuse the app object. This is preferred over `uvicorn.run(app, ...)`.
- `init_db()` is called at module import (so it runs exactly once, on startup). It is **not** called from inside a `@app.on_event("startup")` handler — that pattern is deprecated in modern FastAPI.

### 6.3 No rate limiting, no CSRF (VULN-7, VULN-8)

Do **not** add `slowapi`, `fastapi-limiter`, or any custom rate-limiting middleware.
Do **not** add CSRF token generation, validation, or SameSite cookie hardening.

---

## Phase 7 — Frontend Templates

**Files to create:**
- `frontend/templates/login.html`
- `frontend/templates/signup.html`
- `frontend/templates/dashboard.html`

### 7.1 Shared structure

All three templates share:
- A `<head>` with `<meta charset="utf-8">`, `<meta name="viewport" content="width=device-width, initial-scale=1.0">`, `<title>`, and a `<link rel="stylesheet" href="/static/css/styles.css">`.
- A fixed header (70px tall) with:
  - Left: app title (e.g. "Vulnerable Web Lab" or "Security Vulnerability Lab").
  - Right: three `<img>` tags, 54×54px, in this order — `/static/images/PUCIT_Logo.png`, `/static/images/blue-logo-scl2.png`, `/static/images/excaliat-logo.png`.
- The body has top padding equal to the header height so content isn't hidden.

### 7.2 `login.html`

**Layout:** two-column 50/50 split-screen (see `app-foundation.md` §5.3 for full visual design).

**Left panel** (decorative):
- Deep blue gradient background (`#0d1b5e` → `#1a237e` → `#283593`).
- Content (top to bottom): a small uppercase badge label, a welcome heading, a short description, a bullet list of 3–4 features.
- Two or three semi-transparent white circles (~7% opacity) as decorative overlays.

**Right panel** (form):
- White background, max-width 400px, vertically centered.
- Form heading + subtitle.
- `<form id="loginForm">` with `<input name="username">` and `<input name="password" type="password">`.
- An error message `<div id="error" hidden>...</div>` styled as light-red-background / red-border / dark-red-text.
- A full-width submit button (background `#1a237e`, white text).
- A signup link below: "Don't have an account? Sign up" → `/signup`.

**Critical JS behavior (inline `<script>` at the bottom):**
```js
document.getElementById("loginForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const res = await fetch("/login", { method: "POST", body: formData });
    const data = await res.json();
    if (data.success) {
        window.location.href = data.redirect;  // → /welcome
    } else {
        const err = document.getElementById("error");
        err.textContent = data.error;
        err.hidden = false;
    }
});
```
- `e.preventDefault()` is mandatory.
- The success path **must** use `window.location.href` (not `window.location.replace` or any SPA router).
- The error path **must not** reload the page.

### 7.3 `signup.html`

**Layout:** identical split-screen structure to `login.html`.

**Form fields (4):** `username`, `email`, `password`, `confirm_password`.

**Form is a standard form submit (no `fetch`):**
```html
<form action="/signup" method="POST">
    <input name="username" required>
    <input name="email" type="email" required>
    <input name="password" type="password" required>
    <input name="confirm_password" type="password" required>
    <span id="mismatch" hidden style="color: red;">Passwords do not match</span>
    <button type="submit">Sign Up</button>
</form>
```

**Client-side JS:**
```js
document.querySelector("form").addEventListener("submit", (e) => {
    const p = document.querySelector("[name=password]").value;
    const c = document.querySelector("[name=confirm_password]").value;
    if (p !== c) {
        e.preventDefault();
        document.getElementById("mismatch").hidden = false;
    }
});
```

### 7.4 `dashboard.html`

**Body background:** `#eef1f8`.

**Hero banner** (directly under the fixed header):
- Background: linear gradient `#1a237e` → `#3949ab` (left to right).
- **Left section:** title "Security Vulnerability Lab", subtitle (e.g. "Explore, exploit, and learn").
- **Right section:** the literal placeholder `{{username}}` (no quotes, no braces escaping) followed by a logout `<a>` button (semi-transparent white on gradient).

The route handler does `html.replace("{{username}}", session["username"])` (VULN-2) before responding.

**Content area** (max-width 1100px, centered):
- **Mission card:** white surface, title "Our Mission" (or similar), one paragraph of description.
- **"Vulnerabilities to Discover" section:**
  - Header: uppercase, small, bold.
  - Two-column grid of 8 cards (each is a `<div class="vuln-card">`).
  - Each card contains a colored pill `<span class="tag">` and a description.
  - **Vulnerability tag colors** (per `app-foundation.md` §5.5): SQLi=yellow, XSS=red, Session=purple, Brute=orange, Crypto=green, Exposed=blue, CSRF=pink. The 8th vulnerability tag (CSRF) uses pink.
- **Process steps:** three cards with `#1a237e` background, white text, circular numbered badges 1/2/3, and labels "Find", "Exploit", "Mitigate".

The vulnerability card list and the tag-color-to-vulnerability mapping must match PRD §3.2 / `app-foundation.md` §5.5. If a particular card uses a different tag color, that's a spec drift to flag, not to silently change.

---

## Phase 8 — Styling (`styles.css`)

**File to create:** `frontend/static/css/styles.css`

**Required coverage (from `app-foundation.md` §5):**

| Section | Required CSS |
|---------|--------------|
| Global | `font-family: "Segoe UI", system-ui, -apple-system, sans-serif;` on `body` |
| Header | `position: fixed; top: 0; height: 70px; background: white; box-shadow: 0 2px 10px rgba(26,35,126,0.08);` |
| Inputs | `background: #f8f9ff; border: 1.5px solid #c5cae9; border-radius: 8px;` with `:focus { border-color: #3949ab; box-shadow: 0 0 0 3px rgba(57,73,171,0.12); }` |
| Buttons | `border-radius: 8px;` |
| Cards | `border-radius: 10-12px;` |
| Status tags | `border-radius: 6px;` |
| Auth pages | `@media (min-width: 768px)`: 50/50 grid; `@media (max-width: 767px)`: stack vertically |
| Dashboard grid | `@media (min-width: 768px)`: 2 columns; `@media (max-width: 767px)`: 1 column |
| Process steps | desktop: side-by-side; mobile: stacked |

**Typography scale** (apply via classes or element selectors as appropriate):

| Element | Size | Weight |
|---------|------|--------|
| `.hero-title`, `h1.page-title` | 2rem | 800 |
| `.section-title` | 1.4rem | 700 |
| `.form-title` | 1.7rem | 700 |
| `.card-title`, `.vuln-card h3` | 0.95rem | 700 |
| `body` | 0.9rem | 400 |
| `label` | 0.82rem | 600 |
| `button` | 1rem | 600 |

The CSS does not need to be hand-tuned to match a pixel-perfect design — the values in `app-foundation.md` §5.1 are the source of truth. The point is that the visual **system** (tokens, breakpoints, layout) matches; pixel-level deviations are acceptable as long as the system is internally consistent.

---

## Phase 9 — Documentation

**File to create:** `CLAUDE.md` (at project root)

**Note:** `CLAUDE.md` already exists in this repository (it was created in an earlier phase of the spec-driven workflow). The implementation phase should **review** the existing file and **update** it only if the implementation reveals new information — for example, if the actual port, paths, or architecture diverge from what the existing CLAUDE.md says.

**Skip creating CLAUDE.md from scratch** if the existing file already covers:
- Project context (purpose, "vulnerabilities are features" framing)
- Common commands (`uv sync`, `uv run backend/app/main.py`, port 3001)
- Architecture (three layers, login returns JSONResponse, signup returns Redirect)
- Vulnerability map (all 8 with locations)
- Spec hierarchy (PRD → TDD → prompts → `.claude/specs/`)
- Spec drift (the flat vs. `backend/` package layout discrepancy)

If any of those is missing or wrong after the build, edit the existing file. Do not create a second `CLAUDE.md`.

---

## Phase 10 — Testing and Validation

This phase is **manual** — there is no automated test suite. Run through these checks end-to-end after the build is complete.

### 10.1 Start the app

```powershell
# from project root
uv run backend/app/main.py
```

Expected: server logs `Uvicorn running on http://0.0.0.0:3001`. The `vulnerable_app.db` file appears in the project root. No errors.

If the app fails to start:
- **`ModuleNotFoundError: No module named 'app'`** → the `sys.path` bootstrap in `main.py` is missing or in the wrong order.
- **`OSError: [Errno 98] Address already in use`** → another process is on port 3001; change `PORT` env var or kill the other process.

### 10.2 Page-load smoke tests

In a browser, navigate to each of:
- `http://localhost:3001/` → should redirect to `/signup`.
- `http://localhost:3001/signup` → should render the signup split-screen page.
- `http://localhost:3001/login` → should render the login split-screen page.
- `http://localhost:3001/welcome` (no session) → should redirect to `/login`.

For each: confirm the fixed header is visible, the three logos are 54×54px in the top-right, and the CSS is loaded (split-screen layout on desktop).

### 10.3 Signup flow

1. On `/signup`, enter a fresh username, a valid email, a password, and a matching confirm password.
2. Click submit.
3. **Expected:** redirect to `/login`. Verify the row exists:
   ```powershell
   uv run python -c "import sqlite3; print(sqlite3.connect('vulnerable_app.db').execute('SELECT * FROM users').fetchall())"
   ```

### 10.4 Login flow

1. On `/login`, enter the credentials just created.
2. Click submit.
3. **Expected:** no page reload. The browser navigates to `/welcome`. The hero banner shows the username.

### 10.5 Password mismatch (client-side)

1. On `/signup`, enter mismatched password and confirm_password.
2. **Expected:** inline red error appears, form is not submitted, no network request fires.

### 10.6 Dashboard protection

1. While logged in, visit `/welcome`. Confirm the dashboard renders with the username.
2. Log out via the logout button.
3. Visit `/welcome` again. **Expected:** redirect to `/login`.
4. Manually delete the `session` cookie in DevTools (or use a private window), then visit `/welcome`. **Expected:** redirect to `/login`.

### 10.7 Search reflection

1. With at least one user created, visit:
   ```
   http://localhost:3001/search?q=<username-substring>
   ```
   **Expected:** HTML list containing the matching user(s) (raw HTML, not JSON).
2. Visit with no query: `http://localhost:3001/search`. **Expected:** error string in body.

### 10.8 Database download (VULN-6)

1. **Without** a session, visit:
   ```
   http://localhost:3001/download/db
   ```
2. **Expected:** the browser downloads `vulnerable_app.db`.
3. Open the file in a SQLite client and confirm the user records from §10.3 are present.

### 10.9 SQL injection proof (VULN-1)

1. On `/login`, enter:
   - username: `admin' OR '1'='1' --`
   - password: (anything)
2. **Expected:** login succeeds (with the **first** user in the table). The session is established.

### 10.10 Stored XSS proof (VULN-2)

1. Sign up with username: `<img src=x onerror=alert('XSS-Stored')>` and a real email and password.
2. Log in with those credentials.
3. **Expected:** the alert fires on the dashboard.

### 10.11 Reflected XSS proof (VULN-3)

1. Visit: `http://localhost:3001/search?q=<img src=x onerror=alert('XSS-Reflected')>`
2. **Expected:** the alert fires immediately.

### 10.12 Weak password storage proof (VULN-5)

1. Download the DB (per §10.8).
2. Open in a SQLite client; copy the `password` column for any user.
3. Confirm it is a 32-character hex string (MD5 length).
4. Run: `python -c "import hashlib; print(hashlib.md5(b'<plaintext>').hexdigest())"` — confirm the value matches.

### 10.13 Session hijack proof (VULN-4)

1. Log in normally.
2. In DevTools → Application → Cookies, copy the `session` cookie value.
3. Log out.
4. In a different browser (or a private window), paste the cookie and visit `/welcome`.
5. **Expected:** dashboard renders. The hardcoded weak secret makes this trivial.

### 10.14 No rate limit (VULN-7)

1. In a shell, run a quick loop:
   ```powershell
   1..50 | ForEach-Object { curl -s -o $null -w "%{http_code}`n" -X POST -d "username=foo&password=bar" http://localhost:3001/login }
   ```
2. **Expected:** all 50 return HTTP 401 (or 200 if the first user happened to match), with no throttling, no 429s, no slowdown.

### 10.15 CSRF absence (VULN-8)

1. While logged in, from a **different origin** (e.g. a tiny HTML file on the desktop, opened via `file://`), make a form submit or `fetch` to `http://localhost:3001/login` (or `/signup`) with attacker-chosen credentials.
2. **Expected:** the request succeeds. The server does not check the `Origin` header, does not require a CSRF token, and does not enforce `SameSite=Strict` on the session cookie.

### 10.16 Persistence (AC-06 / TC-15)

1. Create a user.
2. Stop the server (Ctrl+C).
3. Confirm `vulnerable_app.db` is still on disk.
4. Restart with `uv run backend/app/main.py`.
5. Log in with the same credentials.
6. **Expected:** login succeeds.

---

## Execution Order (Summary)

1. **Phase 1** — create directory skeleton.
2. **Phase 2** — `session.py` (DB layer).
3. **Phase 3** — `security.py` (MD5 helpers).
4. **Phase 4** — `auth_service.py` (signup + login with intentional SQLi).
5. **Phase 5** — `auth.py` (route handlers with intentional reflected XSS + exposed DB).
6. **Phase 6** — `main.py` (FastAPI app, sys.path fix, hardcoded secret, static mounts).
7. **Phase 7** — `login.html`, `signup.html`, `dashboard.html` (note the login JS contract carefully).
8. **Phase 8** — `styles.css` (full visual system).
9. **Phase 9** — review and update the existing `CLAUDE.md` if needed.
10. **Phase 10** — run the manual validation checks.

Each phase produces files that the next phase depends on. Phases 1–6 must be done in order before the app can start. Phases 7–8 are independent of each other (both depend on the app booting) and can be done in either order. Phase 9 is review-only. Phase 10 runs against the finished build.

---

**End of Implementation Plan**
