# Implementation Plan: Vulnerable Web Application

**Version:** 1.0.0
**Date:** June 6, 2026
**Reference Documents:**
- [PRD.md](../../docs/PRD.md) — Product requirements
- [TDD.md](../../docs/TDD.md) — Technical design
- [app-foundation.md](./app-foundation.md) — Implementation specification

---

## Overview

This plan describes how to implement an intentionally vulnerable web application for security education. The application is a FastAPI + SQLite + vanilla HTML/CSS/JS stack with **8 deliberate security vulnerabilities**:

| # | Vulnerability | Location | Mechanism |
|---|---------------|----------|-----------|
| 1 | SQL Injection | `auth_service.py` | String concatenation in SQL queries |
| 2 | Stored XSS | `auth.py` (welcome route) | Unescaped username in dashboard template |
| 3 | Reflected XSS | `auth.py` (search route) | Unescaped query parameter in HTML response |
| 4 | Session Hijacking | `main.py` | Hardcoded weak secret key `"super-secret-key-12345"` |
| 5 | Weak Password Storage | `security.py` | MD5 hashing without salt |
| 6 | Exposed Database | `auth.py` (download route) | Unauthenticated `/download/db` endpoint |
| 7 | No Rate Limiting | Global | No rate limiting middleware on any endpoint |
| 8 | CSRF | Global | No CSRF token validation on any form |

> **IMPORTANT**: All vulnerabilities are **intentional** for educational purposes. SQL queries in `auth_service.py` and `auth.py` **MUST** use string concatenation — never parameterized queries.

---

## Phase 1: Project Structure

### Goal
Create the complete directory layout for backend and frontend.

### Backend Files to Create

```
backend/
├── app/
│   ├── __init__.py              # Empty
│   ├── main.py                  # Application entry point
│   ├── core/
│   │   ├── __init__.py          # Empty
│   │   └── security.py          # Password hashing (MD5, no salt)
│   ├── db/
│   │   ├── __init__.py          # Empty
│   │   └── session.py           # SQLite connection and init
│   ├── services/
│   │   ├── __init__.py          # Empty
│   │   └── auth_service.py      # Authentication business logic
│   └── api/
│       ├── __init__.py          # Empty
│       └── routes/
│           ├── __init__.py      # Empty
│           └── auth.py          # HTTP route handlers
└── pyproject.toml               # Backend package config
```

### backend/pyproject.toml

- Build system: `hatchling`
- Package name: `vulnerable-app`
- Python requirement: `>=3.9`
- Dependencies:
  - `fastapi>=0.109.0`
  - `uvicorn>=0.27.0`
  - `python-multipart>=0.0.6`
  - `itsdangerous>=2.0.0`
- Optional dev dependencies:
  - `pytest`

### Frontend Files to Create

```
frontend/
├── templates/
│   ├── login.html               # Login page
│   ├── signup.html              # Registration page
│   └── dashboard.html           # Protected dashboard
└── static/
    ├── css/
    │   └── styles.css           # Application styling
    └── images/                  # Already exists with logos
        ├── PUCIT_Logo.png       # Already present
        ├── blue-logo-scl2.png   # Already present
        └── excaliat-logo.png    # Already present
```

### Empty `__init__.py` Files

Create 6 empty `__init__.py` files:
- `backend/app/__init__.py`
- `backend/app/core/__init__.py`
- `backend/app/db/__init__.py`
- `backend/app/services/__init__.py`
- `backend/app/api/__init__.py`
- `backend/app/api/routes/__init__.py`

---

## Phase 2: Database Layer

### File: `backend/app/db/session.py`

### Functions

#### `get_db() -> sqlite3.Connection`
- Connect to `vulnerable_app.db` at the **project root** (two levels above `backend/app/db/`).
- Use `check_same_thread=False` to allow connection sharing across threads.
- Set `row_factory = sqlite3.Row` for dict-style access to query results.
- Return the connection object.
- No connection pooling — each call opens a fresh connection.

#### `init_db() -> None`
- Call `get_db()` to obtain a connection.
- Execute `CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, email TEXT, password TEXT)`.
- Commit and close the connection.

### Database File Location
- The database file `vulnerable_app.db` is stored at the **project root** (same level as `backend/` and `frontend/` directories).
- Path resolution: use `os.path.dirname(__file__)` to find the `db/` directory, then navigate up to the project root.

---

## Phase 3: Security Utilities

### File: `backend/app/core/security.py`

### Functions

#### `hash_password(password: str) -> str`
- Use `hashlib.md5(password.encode()).hexdigest()`.
- **No salt** — this is intentional (**Vulnerability #5: Weak Password Storage**).
- Returns the hex digest string.

#### `verify_password(plain: str, hashed: str) -> bool`
- Compute `hash_password(plain)` and compare with `hashed`.
- Return `True` if they match, `False` otherwise.

---

## Phase 4: Business Logic

### File: `backend/app/services/auth_service.py`

### Imports
- `from app.db.session import get_db`
- `from app.core.security import hash_password`
- `from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse`
- `from starlette.requests import Request`

### Functions

#### `signup(username: str, email: str, password: str)`

1. Validate that `username`, `email`, and `password` are all non-empty. If any is empty, return `HTMLResponse` with error message.
2. Hash the password: `hashed = hash_password(password)`.
3. Build the INSERT query via **string concatenation** (**Vulnerability #1: SQL Injection**):
   ```python
   query = "INSERT INTO users (username, email, password) VALUES ('" + username + "', '" + email + "', '" + hashed + "')"
   ```
4. Get a database connection via `get_db()`.
5. Execute the query. Commit.
6. On success: return `RedirectResponse(url="/login", status_code=302)`.
7. On `sqlite3.IntegrityError` (UNIQUE constraint violation): catch the exception and return `HTMLResponse` with content indicating "Username already exists" (or similar).

#### `login(request: Request, username: str, password: str)`

1. Validate that `username` and `password` are non-empty. If either is empty, return `JSONResponse` with `{"error": "..."}` and `status_code=401`.
2. Hash the password: `hashed = hash_password(password)`.
3. Build the SELECT query via **string concatenation** (**Vulnerability #1: SQL Injection**):
   ```python
   query = "SELECT * FROM users WHERE username = '" + username + "' AND password = '" + hashed + "'"
   ```
4. Get a database connection via `get_db()`.
5. Execute the query. Fetch one row.
6. If a row is found:
   - Set `request.session["user_id"] = row["id"]`
   - Set `request.session["username"] = row["username"]`
   - Set `request.session["email"] = row["email"]`
   - Return `JSONResponse({"success": True, "redirect": "/welcome"})`
7. If no row is found:
   - Return `JSONResponse({"error": "Invalid username or password"}, status_code=401)`

### Critical: Response Format Asymmetry
- **Signup** returns `RedirectResponse` (HTML redirect) on success and `HTMLResponse` on error.
- **Login** returns `JSONResponse` on both success and failure — consumed by client-side `fetch()` JavaScript.

---

## Phase 5: Route Handlers

### File: `backend/app/api/routes/auth.py`

### Setup
- Create a single `APIRouter` instance.
- Import `auth_service` functions, `get_db`, template path utilities.
- Define a helper to resolve template paths: `frontend/templates/` relative to project root.

### Routes

#### `GET /` → Redirect to signup
```python
@router.get("/")
async def index():
    return RedirectResponse(url="/signup", status_code=302)
```

#### `GET /signup` → Serve signup form
- Read `frontend/templates/signup.html` from disk.
- Return `HTMLResponse(content=html)`.
- Template is read on **every request** — no caching.

#### `POST /signup` → Process registration
- Receive `username`, `email`, `password` via `Form()` parameters.
- Call `auth_service.signup(username, email, password)`.
- Return the result (either redirect or error HTML).

#### `GET /login` → Serve login form
- Read `frontend/templates/login.html` from disk.
- Return `HTMLResponse(content=html)`.

#### `POST /login` → Process authentication
- Receive `request: Request`, `username`, `password` via `Form()` parameters.
- Call `auth_service.login(request, username, password)`.
- Return the result (JSON response).

#### `GET /download/db` → Serve database file (**Vulnerability #6**)
- Return `FileResponse(path_to_db, filename="vulnerable_app.db")`.
- **No authentication check** — anyone can download the database.

#### `GET /search` → Search users (**Vulnerability #3**)
- Receive `q: str` as a query parameter.
- If `q` is empty or missing, return an appropriate response.
- Build SQL query via **string concatenation**:
  ```python
  query = "SELECT username, email FROM users WHERE username LIKE '%" + q + "%' OR email LIKE '%" + q + "%'"
  ```
- Execute query, fetch results.
- Build HTML response with results as `<li>` elements:
  ```python
  f"<li>{row[0]} ({row[1]})</li>"
  ```
- The query parameter `q` is **directly interpolated into the HTML** without escaping (**Vulnerability #3: Reflected XSS**).
- On exception: return error string containing `str(e)` (information leakage).

#### `GET /welcome` → Protected dashboard (**Vulnerability #2**)
- Check `request.session.get("user_id")`. If missing, redirect to `/login`.
- Read `frontend/templates/dashboard.html` from disk.
- Perform string substitution: `html.replace("{{username}}", request.session["username"])`.
- **No HTML escaping** on the username value (**Vulnerability #2: Stored XSS**).
- Return `HTMLResponse(content=html)`.

#### `GET /logout` → Clear session
- Call `request.session.clear()`.
- Return `RedirectResponse(url="/login", status_code=302)`.

---

## Phase 6: Application Entry Point

### File: `backend/app/main.py`

### sys.path Setup
At the top of `main.py`, before any local imports, add the `backend/` directory to `sys.path`:
```python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
```
This ensures the `app` package resolves correctly regardless of the working directory (e.g., `uv run backend/app/main.py` from project root or `python app/main.py` from `backend/`).

### Application Setup
1. Create `FastAPI()` instance with appropriate title.
2. Add `SessionMiddleware` with `secret_key="super-secret-key-12345"` (**Vulnerability #4: Session Hijacking**).
3. Include the auth router from `app.api.routes.auth`.
4. Mount static files:
   - `/static/css` → `frontend/static/css/`
   - `/static/images` → `frontend/static/images/`
5. Call `init_db()` at module level to initialize the database on startup.

### Server Startup
```python
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 3001))
    uvicorn.run(app, host="0.0.0.0", port=port)
```

### Vulnerability Notes
- **No rate limiting middleware** configured (**Vulnerability #7**).
- **No CSRF protection** on any route (**Vulnerability #8**).

---

## Phase 7: Frontend Templates

### Shared Header (all three pages)
- Fixed position, 70px height, white background.
- Bottom border: subtle light border.
- Shadow: `0 2px 10px rgba(26, 35, 126, 0.08)`.
- Left: Application title ("Security Vulnerability Lab" or similar).
- Right: Three logos at 54×54px — PUCIT (`PUCIT_Logo.png`), Excaliat (`excaliat-logo.png`), FCCU (`blue-logo-scl2.png`).
- Image paths: `/static/images/<filename>`.

---

### File: `frontend/templates/login.html`

#### Layout
Two-column 50/50 split-screen.

#### Left Panel (Decorative)
- Background: linear gradient `#0d1b5e → #1a237e → #283593`.
- Content (centered vertically):
  - Badge label (small uppercase, e.g., "SECURITY EDUCATION PLATFORM").
  - Welcome heading (large white bold text).
  - Description paragraph (white text).
  - Bullet list of features (white text).
- Decorative: Semi-transparent white circle overlays at ~7% opacity.

#### Right Panel (Form)
- White background, form centered with max-width 400px.
- Form title: "Sign In" (bold).
- Form subtitle: muted text (e.g., "Enter your credentials to access the lab").
- **Username field**: `<input type="text" name="username">` with label.
- **Password field**: `<input type="password" name="password">` with label.
- **Error message area**: `<div id="error-message">` — hidden by default. Styled with light red background (`#fef2f2`), red border, dark red text (`#991b1b`).
- **Submit button**: Full-width, `#1a237e` background, white text, 8px radius. Text: "Sign In".
- **Signup link**: "Don't have an account? Sign up" linking to `/signup`.

#### JavaScript (inline)
```javascript
// Intercept form submission
form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData(form);
    const response = await fetch('/login', { method: 'POST', body: formData });
    const data = await response.json();
    if (data.success) {
        window.location.href = data.redirect;  // "/welcome"
    } else {
        // Show error message inline
        errorDiv.textContent = data.error;
        errorDiv.style.display = 'block';
    }
});
```

Key: Login uses `fetch()` with JSON responses — **no page reload** on success or failure.

---

### File: `frontend/templates/signup.html`

#### Layout
Identical split-screen structure to login page.

#### Left Panel
Same gradient, same decorative circles, adapted text for registration context.

#### Right Panel (Form)
- Standard HTML form: `<form action="/signup" method="POST">`.
- Form title: "Create Account" (bold).
- Form subtitle: muted text.
- **Username field**: `<input type="text" name="username">`.
- **Email field**: `<input type="email" name="email">`.
- **Password field**: `<input type="password" name="password">`.
- **Confirm Password field**: `<input type="password" id="confirm_password">` — **no `name` attribute** (not sent to server).
- **Password mismatch error**: `<span id="password-error">` — red text below confirm password field, hidden by default.
- **Submit button**: Full-width, same styling as login button. Text: "Create Account".
- **Login link**: "Already have an account? Sign in" linking to `/login`.

#### JavaScript (inline)
```javascript
// Validate password match before submission
form.addEventListener('submit', (e) => {
    const password = document.querySelector('[name="password"]').value;
    const confirm = document.getElementById('confirm_password').value;
    if (password !== confirm) {
        e.preventDefault();
        passwordError.textContent = 'Passwords do not match';
        passwordError.style.display = 'block';
    }
});
```

Key: Signup uses standard form POST — **page reloads** on submission. Client-side password match validation prevents submission on mismatch.

---

### File: `frontend/templates/dashboard.html`

#### Hero Banner
- Directly beneath the fixed header.
- Background: linear gradient `#1a237e → #3949ab`.
- Left section: Title ("Security Vulnerability Lab") and subtitle ("Explore, Exploit, and Learn").
- Right section: "Logged in as **{{username}}**" and a logout button (semi-transparent white, links to `/logout`).

#### Mission Card
- White background, rounded corners (10–12px).
- Section title (e.g., "Our Mission").
- Descriptive paragraph about the platform's educational purpose.

#### Vulnerabilities to Discover Section
- Section header: Uppercase, small, bold text ("VULNERABILITIES TO DISCOVER").
- Two-column grid of 8 vulnerability cards.

##### Vulnerability Cards

| # | Title | Tag Text | Tag Color | Description |
|---|-------|----------|-----------|-------------|
| 1 | SQL Injection | SQLi | Yellow | Raw SQL query construction allows authentication bypass |
| 2 | Stored XSS | XSS | Red | Malicious scripts stored in database execute on page load |
| 3 | Reflected XSS | XSS | Red | User input reflected in search results without escaping |
| 4 | Session Hijacking | Session | Purple | Weak secret key allows session cookie theft and reuse |
| 5 | Weak Password Storage | Crypto | Green | MD5 hashing without salt enables rainbow table attacks |
| 6 | Exposed Database | Exposed | Blue | Database file downloadable without authentication |
| 7 | No Rate Limiting | Brute | Orange | Unlimited login attempts enable brute force attacks |
| 8 | CSRF | CSRF | Pink | No token validation on form submissions |

Each card: white background, rounded corners (10–12px), light border (`#e2e8f0`), hover shadow (`0 4px 16px rgba(26, 35, 126, 0.10)`), colored pill tag with title text, and description text.

#### Process Steps Section
Three cards displayed horizontally:

| Step | Number | Label | Description |
|------|--------|-------|-------------|
| 1 | ① | Find | Identify vulnerabilities in the source code |
| 2 | ② | Exploit | Use real attack vectors to demonstrate impact |
| 3 | ③ | Mitigate | Implement secure coding practices |

Each card: `#1a237e` background, white text, circular numbered badge.

#### Username Placeholder
The template contains `{{username}}` which is replaced server-side via `html.replace('{{username}}', session['username'])`. **No escaping** is applied — this enables Stored XSS (Vulnerability #2).

---

## Phase 8: Styling

### File: `frontend/static/css/styles.css`

Implement the complete visual design specification from [app-foundation.md §5](./app-foundation.md#5-complete-visual-design-specification).

### Global Styles
- Font family: `'Segoe UI', system-ui, -apple-system, sans-serif`.
- Box-sizing: `border-box` on all elements.
- Body margin: 0, padding: 0.

### Typography Scale

| Element | Size | Weight | CSS Target |
|---------|------|--------|------------|
| Main titles | 2rem | 800 | `.hero-title`, `.welcome-heading` |
| Section titles | 1.4rem | 700 | `.section-title`, `.mission-title` |
| Form titles | 1.7rem | 700 | `.form-title` |
| Card titles | 0.95rem | 700 | `.card-title` |
| Body text | 0.9rem | 400 | `body`, `.description` |
| Labels | 0.82rem | 600 | `label`, `.form-label` |
| Buttons | 1rem | 600 | `.btn`, `button` |

### Color Palette
- Primary: `#1a237e`, `#3949ab`, `#283593`, `#0f172a`
- Backgrounds: `#eef1f8`, `#ffffff`, `#f8f9ff`
- Text: `#1e293b`, `#475569`, `#64748b`
- Borders: `#c5cae9`, `#e2e8f0`

### Component Styles

#### Header
- `position: fixed`, `top: 0`, `width: 100%`, `height: 70px`, `z-index: 1000`.
- `background: #ffffff`, `border-bottom: 1px solid #e2e8f0`.
- `box-shadow: 0 2px 10px rgba(26, 35, 126, 0.08)`.
- Flexbox: space-between, items centered.
- Logo images: `width: 54px`, `height: 54px`, `object-fit: contain`.

#### Auth Pages (Login/Signup)
- Container: `display: grid`, `grid-template-columns: 1fr 1fr`, `min-height: 100vh`.
- Left panel: gradient background, `padding-top: 70px` (below fixed header).
- Decorative circles: `position: absolute`, `border-radius: 50%`, `background: rgba(255,255,255,0.07)`.
- Right panel: `display: flex`, `align-items: center`, `justify-content: center`.
- Form: `max-width: 400px`, `width: 100%`.

#### Inputs
- `background: #f8f9ff`.
- `border: 1.5px solid #c5cae9`.
- `border-radius: 8px`.
- `padding: 12px 16px`.
- Focus: `border-color: #3949ab`, `box-shadow: 0 0 0 3px rgba(57, 73, 171, 0.12)`, `outline: none`.

#### Buttons
- `background: #1a237e`, `color: #ffffff`.
- `border: none`, `border-radius: 8px`.
- `padding: 12px`, `width: 100%`.
- `font-size: 1rem`, `font-weight: 600`.
- `cursor: pointer`.
- Hover: slightly lighter background or opacity change.

#### Error Messages
- `background: #fef2f2`.
- `border: 1px solid #fecaca`.
- `color: #991b1b`.
- `border-radius: 8px`, `padding: 12px`.

#### Dashboard
- Body background: `#eef1f8`.
- Hero banner: gradient `#1a237e → #3949ab`, padding, flexbox layout.
- Content container: `max-width: 1100px`, `margin: 0 auto`.
- Cards: `background: #ffffff`, `border-radius: 10px`, `border: 1px solid #e2e8f0`.
- Card hover: `box-shadow: 0 4px 16px rgba(26, 35, 126, 0.10)`, `transition: box-shadow 0.2s`.

#### Vulnerability Tags
- `display: inline-block`, `padding: 4px 10px`, `border-radius: 6px`, `font-size: 0.75rem`, `font-weight: 600`.
- Colors by type:
  - `.tag-sqli`: yellow background (`#fef9c3`), dark yellow text (`#854d0e`)
  - `.tag-xss`: red background (`#fee2e2`), dark red text (`#991b1b`)
  - `.tag-session`: purple background (`#f3e8ff`), dark purple text (`#6b21a8`)
  - `.tag-brute`: orange background (`#ffedd5`), dark orange text (`#9a3412`)
  - `.tag-crypto`: green background (`#dcfce7`), dark green text (`#166534`)
  - `.tag-exposed`: blue background (`#dbeafe`), dark blue text (`#1e40af`)
  - `.tag-csrf`: pink background (`#fce7f3`), dark pink text (`#9d174d`)

#### Process Steps
- Container: flexbox, gap between cards.
- Card: `background: #1a237e`, `border-radius: 12px`, `padding: 24px`, `color: white`.
- Badge: `width: 40px`, `height: 40px`, `border-radius: 50%`, `background: rgba(255,255,255,0.2)`, centered number.

### Responsive Design

```css
@media (max-width: 768px) {
    /* Auth pages: stack vertically */
    .auth-container { grid-template-columns: 1fr; }
    
    /* Dashboard cards: single column */
    .vuln-grid { grid-template-columns: 1fr; }
    
    /* Process steps: vertical */
    .steps-container { flex-direction: column; }
    
    /* Header logos: smaller */
    .header-logo { width: 40px; height: 40px; }
}
```

---

## Phase 9: CLAUDE.md

### File: `CLAUDE.md` (project root)

Create a CLAUDE.md file documenting:

1. **Project Context**: Security education platform with intentional vulnerabilities.
2. **Development Commands**:
   - Install: `cd backend && uv sync`
   - Run: `uv run backend/app/main.py` (from project root)
   - Access: `http://localhost:3001`
3. **Architecture Overview**: Three-layer (presentation, application, data). Backend in `backend/app/`, frontend in `frontend/`.
4. **Vulnerability Map**: Table of 8 vulnerabilities with file locations and line references (to be filled after implementation).
5. **Frontend-Backend Integration**:
   - Login: fetch() → JSON response → client-side redirect
   - Signup: standard form POST → server redirect
   - Dashboard: server-side `{{username}}` replacement
6. **Security Education Context**: All vulnerabilities are intentional. Never use parameterized queries in `auth_service.py`. Never add CSRF tokens. Never change the session secret.
7. **Specification Hierarchy**: PRD.md → TDD.md → app-foundation.md → this plan.

---

## Phase 10: Testing and Validation

### Manual Verification Steps

#### 10.1 Application Startup
1. Run `uv run backend/app/main.py` from project root.
2. Verify server starts on `http://localhost:3001`.
3. Verify `vulnerable_app.db` is created at project root.
4. Verify no errors in console output.

#### 10.2 Page Loading
1. Visit `http://localhost:3001/` — should redirect to `/signup`.
2. Visit `http://localhost:3001/signup` — should display signup form with split-screen layout.
3. Visit `http://localhost:3001/login` — should display login form with split-screen layout.
4. Verify header with logos appears on both pages.
5. Verify responsive layout by resizing browser window.

#### 10.3 Registration Flow
1. Fill in all four fields on signup page (username: `testuser`, email: `test@test.com`, password: `password123`, confirm: `password123`).
2. Submit form → should redirect to `/login`.
3. Verify user exists in database: `sqlite3 vulnerable_app.db "SELECT * FROM users"`.
4. Verify password is stored as MD5 hash (not plaintext).
5. Test password mismatch: enter different confirm password → red error text appears, form does not submit.

#### 10.4 Login Flow
1. Enter valid credentials on login page.
2. Submit → should redirect to `/welcome` (via JavaScript).
3. Verify dashboard shows "Logged in as testuser".
4. Test invalid credentials → error message appears inline without page reload.

#### 10.5 Dashboard
1. Verify hero banner with gradient and username display.
2. Verify mission card renders.
3. Verify 8 vulnerability cards display with correct tag colors.
4. Verify 3 process step cards (Find, Exploit, Mitigate).

#### 10.6 Logout
1. Click logout button on dashboard.
2. Verify redirect to `/login`.
3. Visit `http://localhost:3001/welcome` → should redirect to `/login`.

#### 10.7 Route Protection
1. Open a new browser/incognito window.
2. Visit `http://localhost:3001/welcome` without logging in → should redirect to `/login`.

#### 10.8 Vulnerability Verification
1. **Exposed Database**: Visit `http://localhost:3001/download/db` without auth → database file downloads.
2. **Reflected XSS**: Visit `http://localhost:3001/search?q=<img src=x onerror=alert(1)>` → verify query is reflected in response.
3. **Session Secret**: Inspect code for hardcoded `"super-secret-key-12345"`.
4. **MD5 Hashing**: Check password in database is 32-character hex string (MD5).
5. **SQL Injection**: Verify string concatenation in `auth_service.py` (code review).
6. **CSRF**: Verify no CSRF tokens in form HTML (code review).
7. **Rate Limiting**: Verify no rate limiting middleware in `main.py` (code review).

#### 10.9 Persistence
1. Stop the application (Ctrl+C).
2. Restart: `uv run backend/app/main.py`.
3. Login with previously created credentials → should succeed.
4. Verify data persisted across restart.

#### 10.10 Database Recreation
1. Stop the application.
2. Delete `vulnerable_app.db`.
3. Restart the application.
4. Verify new empty database is created.
5. Register a new user → should succeed.

---

## Implementation Order Summary

| Order | Phase | Files | Dependencies |
|-------|-------|-------|--------------|
| 1 | Project Structure | Directories, `__init__.py` files, `backend/pyproject.toml` | None |
| 2 | Database Layer | `backend/app/db/session.py` | Phase 1 |
| 3 | Security Utilities | `backend/app/core/security.py` | Phase 1 |
| 4 | Business Logic | `backend/app/services/auth_service.py` | Phases 2, 3 |
| 5 | Route Handlers | `backend/app/api/routes/auth.py` | Phase 4 |
| 6 | Entry Point | `backend/app/main.py` | Phase 5 |
| 7 | Templates | `frontend/templates/*.html` | Phase 6 (for testing) |
| 8 | Styling | `frontend/static/css/styles.css` | Phase 7 |
| 9 | CLAUDE.md | `CLAUDE.md` | All phases |
| 10 | Testing | Manual verification | All phases |

Each phase should be completed and verified before moving to the next. Phases 2 and 3 can be implemented in parallel as they have no interdependencies.
