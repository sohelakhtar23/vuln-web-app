# Software Specification Document (Implementation Addendum)

**Project:** Vulnerable Web Application — Security Lab
**Document Type:** Implementation Addendum
**Audience:** Engineers reproducing the application from spec
**Companion documents:** `docs/PRD.md`, `docs/TDD.md`

---

## 1. Scope

This document captures **implementation-level behavior** required to reproduce the Vulnerable Web Application exactly. It is intentionally additive: it describes *how the system behaves at runtime* without restating product goals, system architecture, technology stack, vulnerability catalog, database schema, or endpoint inventory already documented in `PRD.md` and `TDD.md`.

**In scope here:** runtime mechanics, user flows, functional requirements, visual design tokens, form contracts, validation rules, session state, data lifecycle, success/alternate paths, edge cases, business rules, rebuild requirements, acceptance criteria, test cases, and known documentation gaps.

**Out of scope here** (see PRD/TDD): why the app exists, who uses it, the OWASP categorization of the 8 intentional flaws, the exact SQL DDL, the high-level layered architecture, the data-flow diagrams.

---

## 2. Runtime Behavior

The application has the following observable runtime characteristics, all of which a faithful reproduction must match:

- **Automatic database initialization on startup.** The `users` table is created via `CREATE TABLE IF NOT EXISTS` during application boot, before the first request is served.
- **Missing DB files recreated automatically.** If `vulnerable_app.db` does not exist on disk, the SQLite driver creates it on first connection; `init_db()` then ensures the `users` table exists.
- **Data preserved across restarts.** User records inserted at signup persist across process restarts. There is no in-memory cache, no fixtures, no seed data.
- **Static assets available after boot.** CSS and images are mounted by FastAPI/Starlette at the paths `/static/css/*` and `/static/images/*` and are served directly from `frontend/static/` on disk.
- **Templates loaded from disk at request time with no caching.** `signup.html`, `login.html`, and `dashboard.html` are read from disk on every request. There is no Jinja2 `TemplateResponse` cache, no precompiled templates. Editing a template file on disk and refreshing the browser reflects the change immediately.
- **Dashboard content modified via runtime string substitution before response.** The welcome handler reads `dashboard.html` and performs `html.replace('{{username}}', username)` against the raw HTML string. This substitution is intentionally not done via a templating engine — it is a literal `str.replace`.
- **Authentication state based solely on session presence.** A request to a protected route succeeds if and only if `user_id` exists in the request session. There is no token validation, no signature re-verification beyond what Starlette's `SessionMiddleware` does on the cookie itself, and no DB lookup to confirm the user still exists.

---

## 3. User Flows

### 3.1 Registration

1. User navigates to `/signup`.
2. Server reads `signup.html` from disk and returns it as an HTML response.
3. User fills in the form: username, email, password, confirm password.
4. **Client-side validation** (JavaScript on the signup page) checks that `password === confirm_password`; if they do not match, an inline red error message appears beneath the confirm field and the form is **not** submitted.
5. On valid match, the browser performs a standard form POST to `/signup` (no `fetch`, no JSON — a real form submit).
6. Server receives `username`, `email`, `password` via FastAPI `Form()`.
7. Server hashes the password (MD5, no salt), constructs an `INSERT INTO users ...` SQL string via concatenation, and executes it.
8. On success: server returns a `RedirectResponse` (HTTP 302) to `/login`.
9. User lands on the login page.

### 3.2 Login

1. User navigates to `/login`.
2. Server reads `login.html` from disk and returns it as an HTML response.
3. User fills in username and password.
4. The login page's JavaScript **prevents the default form submit**, builds `FormData`, and issues an async `fetch('/login', { method: 'POST', body: formData })`.
5. Server receives the POST, hashes the input password (MD5, no salt), and builds a `SELECT * FROM users WHERE username = '...' AND password = '...'` query via string concatenation.
6. Server returns a **JSON response** (not a redirect): `{"success": true, "redirect": "/welcome"}` on match, or HTTP 401 with `{"success": false, "error": "Invalid credentials"}` on mismatch.
7. **On success:** the client-side JS reads `data.redirect`, sets `window.location.href = '/welcome'`, and the browser performs a full navigation. The server has already set the session cookie (`user_id`, `username`, `email`) in the response.
8. **On failure:** the client-side JS displays the error message inline (no page reload, no redirect) so the user can retry.

### 3.3 Dashboard

1. User navigates to `/welcome` (typically after a successful login).
2. Server checks `request.session` for `user_id`.
3. **If absent:** server returns a `RedirectResponse` to `/login`. The user cannot view the dashboard.
4. **If present:** server reads `dashboard.html` from disk.
5. Server performs `html.replace('{{username}}', session['username'])` on the HTML string.
6. Server returns the substituted HTML response.
7. The username appears in the hero banner and elsewhere where the `{{username}}` placeholder is used in the template.

### 3.4 Logout

1. User clicks the logout button/link in the dashboard (typically a `GET /logout` link).
2. Server calls `request.session.clear()` to remove all session keys.
3. Server returns a `RedirectResponse` to `/login`.
4. On the next request to a protected route (e.g. `/welcome`), the absence of `user_id` causes a redirect to `/login`. **Protected resources are inaccessible** until a fresh successful login re-establishes the session.

---

## 4. Functional Requirements

| ID | Title | Requirement |
|----|-------|-------------|
| **FR-01** | Session Management | The application maintains a Starlette session with three stored values after a successful login: `user_id` (integer), `username` (string), `email` (string). Sessions are signed cookies (`itsdangerous`), keyed by a hardcoded secret (see TDD §3.1.1). |
| **FR-02** | Dynamic User Context | The dashboard response is personalized at request time: the authenticated user's `username` is injected into the dashboard HTML via string substitution of the `{{username}}` placeholder. The substitution is `str.replace`, not a templating engine. |
| **FR-03** | Route Protection | The `/welcome` route is the only protected route. Protection is enforced by checking `'user_id' in request.session`; absence triggers a redirect to `/login`. All other routes (`/`, `/signup`, `/login`, `/search`, `/download/db`, `/logout`) are publicly accessible. |
| **FR-04** | Error Handling | Login failures return a JSON error body with HTTP 401 so client-side JS can display the error inline. Signup failures (e.g. duplicate username) return an HTML response containing the literal error string. Unhandled exceptions on `/search` are caught and the raw exception message (`str(e)`) is included in the response body. |
| **FR-05** | Search Processing | `GET /search?q=<query>` executes a SQL query that uses `LIKE '%' + q + '%'` against `username` and `email`. Results are returned as an HTML response where each row is rendered as an `<li>` containing the username and email. The query parameter is interpolated into both the SQL and the response HTML without escaping. An empty `q` returns an error string. |
| **FR-06** | Persistence | User records persist in `vulnerable_app.db` (SQLite, project root) across process restarts. The DB is created on first run if absent, and the `users` table is created via `CREATE TABLE IF NOT EXISTS` on every boot. There is no migration system. |

---

## 5. Complete Visual Design Specification

This section is the source of truth for the visual presentation. Implementers must reproduce the tokens, layout, and responsive behavior exactly.

### 5.1 Global Design System

**Typography stack:**
```css
font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
```

**Typography scale:**

| Role | Size | Weight |
|------|------|--------|
| Main titles (page hero, banner) | 2rem | 800 |
| Section titles (cards, panels) | 1.4rem | 700 |
| Form titles (login/signup form heading) | 1.7rem | 700 |
| Card titles (vulnerability cards, process steps) | 0.95rem | 700 |
| Body text | 0.9rem | 400 |
| Labels (form labels) | 0.82rem | 600 |
| Buttons | 1rem | 600 |

**Primary colors:**

| Token | Hex |
|-------|-----|
| Indigo Deep | `#1a237e` |
| Indigo Mid | `#3949ab` |
| Indigo Dark | `#283593` |
| Navy Near-Black | `#0f172a` |
| Page Background | `#eef1f8` |
| Surface White | `#ffffff` |

**Text colors:**

| Token | Hex | Use |
|-------|-----|-----|
| Heading Text | `#1e293b` | Dark text on light backgrounds |
| Body Text | `#475569` | Paragraphs and long-form |
| Muted Text | `#64748b` | Subtitles, helper text |
| Inverse Muted | `#c5cae9` | Light text on dark gradient panels |
| Brand Text | `#1a237e` | Links, brand-colored headings |

**Border radius:**

| Element | Radius |
|---------|--------|
| Inputs | 8px |
| Buttons | 8px |
| Cards | 10–12px |
| Status tags / pills | 6px |

**Shadows:**

| Element | Shadow |
|---------|--------|
| Header | `0 2px 10px rgba(26, 35, 126, 0.08)` |
| Card hover | `0 4px 16px rgba(26, 35, 126, 0.10)` |
| Input focus glow | `0 0 0 3px rgba(57, 73, 171, 0.12)` |

### 5.2 Shared Header

- **Position:** `fixed` at top of viewport.
- **Height:** 70px.
- **Background:** white.
- **Border:** 1px solid bottom border, subtle.
- **Shadow:** as defined in the shadow table above.
- **Layout:** two zones — app title on the left, three organizational logos (54×54px each) on the right.
- **Logos** (in order, left to right): PUCIT, blue-logo-scl2, excaliat.

### 5.3 Login Page

**Layout:** two-column 50/50 split-screen on desktop.

**Left panel** (decorative):
- Background: deep blue gradient `#0d1b5e` → `#1a237e` → `#283593`.
- Content: a small "badge" label (uppercase, light text), a welcome heading, a short description paragraph, and a bullet list of features/values.
- Decorative overlay: 2–3 semi-transparent white circles at ~7% opacity, positioned to add visual interest without obscuring text.

**Right panel** (form):
- Background: white.
- Form: max-width 400px, centered within the right panel.
- Form fields in order: title, subtitle, username input, password input, error message area, full-width login button, signup link.
- **Login button:** background `#1a237e`, text white, full width, 8px radius.
- **Input styling:** background `#f8f9ff`, border 1.5px solid `#c5cae9`, 8px radius. On focus, border becomes `#3949ab` and the input gets the focus glow shadow.
- **Error message area:** light red background, red border, dark red text — appears inline (not as a modal or alert) when login fails. The form is not reloaded.

### 5.4 Signup Page

- **Layout:** identical to login — same split-screen, same gradient panel, same decorative circles, same right-panel form.
- **Form fields:** username, email, password, confirm password.
- **Password mismatch handling:** client-side JavaScript compares `password` to `confirm_password` on form submit. If they differ, a red error message appears directly below the confirm field, **and the form is not submitted**. The page is not reloaded.

### 5.5 Dashboard

**Page background:** `#eef1f8`.

**Hero banner:** sits beneath the fixed header. Background: gradient `#1a237e` → `#3949ab` (left to right).
- **Left section:** title (e.g. "Security Vulnerability Lab") and subtitle.
- **Right section:** the logged-in username (white text) and a semi-transparent white logout button.

**Content area:** max-width 1100px, centered.

**Mission card:** white surface, contains a section title and a descriptive paragraph about the lab's purpose.

**"Vulnerabilities to Discover" section:**
- Header: uppercase, small, bold.
- Layout: two-column grid of 8 cards (collapses to one column on mobile).
- Each card: white background, 10–12px radius, light border, hover shadow (as defined).
- Each card contains: a colored pill tag (status badge) and a description of the vulnerability.

**Vulnerability tag colors:**

| Tag | Color |
|-----|-------|
| SQLi | Yellow |
| XSS | Red |
| Session | Purple |
| Brute | Orange |
| Crypto | Green |
| Exposed | Blue |
| CSRF | Pink |

(One tag color per vulnerability; see PRD §3.2 for the catalog of 8 flaws and their corresponding tag.)

**Process step cards:** three cards, each with:
- Background `#1a237e`, white text.
- A circular numbered badge (1, 2, 3).
- Step label: "Find", "Exploit", "Mitigate".

### 5.6 Responsive Behavior

| Breakpoint behavior | Desktop | Mobile |
|---------------------|---------|--------|
| Auth pages | 50/50 split-screen | Stack vertically (left panel above form) |
| Dashboard vulnerability grid | Two columns | Single column |
| Process step cards | Side-by-side | Stacked vertically |
| Header logos | 54×54px | Shrink proportionally |

---

## 6. Form Specifications

### 6.1 Registration Form

- **Method:** `POST` to `/signup` (standard form submit, no `fetch`).
- **Inputs (4):**
  1. `username` (text, required)
  2. `email` (email, required)
  3. `password` (password, required)
  4. `confirm_password` (password, required)
- **Client-side validation:** JavaScript on submit compares `password` and `confirm_password`. Mismatch → inline red error, form not submitted. Match → form submits normally.
- **Server response:** on success, `RedirectResponse` (302) to `/login`. On duplicate username, an HTML response containing the error string (rendered into the page).

### 6.2 Login Form

- **Method:** `POST` to `/login` via async `fetch()` from JavaScript — **not** a standard form submit.
- **Inputs (2):**
  1. `username` (text, required)
  2. `password` (password, required)
- **Submission:** JavaScript prevents the default form submission, constructs a `FormData` from the form, and issues `fetch('/login', { method: 'POST', body: formData })`.
- **Server response:** JSON, not HTML.
  - Success: HTTP 200, `{"success": true, "redirect": "/welcome"}`. Client sets `window.location.href = data.redirect`.
  - Failure: HTTP 401, `{"success": false, "error": "Invalid credentials"}`. Client displays `data.error` inline.
- **Page is never reloaded** during the login attempt.

---

## 7. Validation Rules

| Form / Endpoint | Field | Rule |
|-----------------|-------|------|
| Registration | username | Required; uniqueness enforced at DB level (SQLite `UNIQUE` constraint on `users.username`). |
| Registration | email | Required. |
| Registration | password | Required. |
| Registration | confirm_password | Required; must match `password` (client-side check). |
| Login | username | Required. |
| Login | password | Required. |
| Search | `q` | Required; empty string returns an error response. |

The only validation in the signup POST path beyond presence checks is the database-level uniqueness constraint on `username`. There is no email format validation, no password strength check, and no input length cap.

---

## 8. Session State Model

**Stored values (set on successful login):**

| Key | Type | Source |
|-----|------|--------|
| `user_id` | int | `users.id` from the row that matched the login query |
| `username` | str | `users.username` from the same row |
| `email` | str | `users.email` from the same row |

**Lifecycle:**

1. **Creation:** values are written to `request.session` inside the `login()` service function on a successful authentication. The session cookie is set on the response that returns `{"success": true}` to the login form's `fetch()`.
2. **Usage during route access:** every protected-route handler reads `request.session` to determine auth state. The dashboard handler reads `request.session['username']` to perform the `{{username}}` substitution.
3. **Destruction:** the `/logout` handler calls `request.session.clear()`. The next request to a protected route finds no `user_id` and is redirected to `/login`.

There is no session expiration, idle timeout, or sliding renewal. The cookie is signed with the hardcoded secret (see TDD §3.1.1 and PRD §3.2 VULN-4).

---

## 9. Data Lifecycle Rules

- **Creation:** a user record is created only via the signup form. The `id` is auto-assigned by SQLite; `created_at` is not stored.
- **Modification:** no workflow exists. There is no profile-edit endpoint, no password-change endpoint, and no admin user-management endpoint.
- **Deletion:** no workflow exists. Users cannot be deleted via the UI or any API.
- **Recovery:** no password reset, no account recovery, no email verification.
- **Inspection:** the `users` table can be inspected directly by reading `vulnerable_app.db` with a SQLite client, or by hitting the unauthenticated `/download/db` endpoint.

---

## 10. Success Paths

| ID | Path | Steps |
|----|------|-------|
| **SP-01** | Successful registration | User submits signup form with valid new username, matching password/confirm → server inserts user → 302 redirect to `/login`. |
| **SP-02** | Successful login | User submits login form with valid credentials via `fetch()` → server authenticates → server sets session cookie → server returns `{"success": true, "redirect": "/welcome"}` → client navigates to `/welcome`. |
| **SP-03** | Successful dashboard view | Authenticated user requests `/welcome` → server finds `user_id` in session → server reads `dashboard.html` → server performs `html.replace('{{username}}', session['username'])` → server returns HTML. |
| **SP-04** | Successful logout | User clicks logout link → server clears session → 302 redirect to `/login` → subsequent `/welcome` request is redirected back to `/login`. |

---

## 11. Alternate Paths

| ID | Path | Behavior |
|----|------|----------|
| **AP-01** | Duplicate username on signup | Server catches the SQLite `UNIQUE` constraint exception → returns an HTML response containing the literal error string "Username already exists" (or the exception text) → user sees the error on the signup page. |
| **AP-02** | Invalid credentials on login | Server's SQL query returns no rows → server returns HTTP 401 with `{"success": false, "error": "Invalid credentials"}` → client displays the error inline. The form is not reloaded. |
| **AP-03** | Unauthorized dashboard access | Unauthenticated user requests `/welcome` → server finds no `user_id` in session → 302 redirect to `/login`. The dashboard HTML is never read. |
| **AP-04** | Empty search query | User requests `/search` with no `q` parameter (or empty `q`) → server returns an error string in the response body. |

---

## 12. Edge Cases

| ID | Case | Expected behavior |
|----|------|-------------------|
| **EC-01** | Existing username on signup | SQLite `UNIQUE` violation is caught; HTML error response returned; user is not created. |
| **EC-02** | Empty registration submission | Server-side check rejects missing fields; HTML error response returned. |
| **EC-03** | Empty login submission | Server-side check rejects missing fields; login attempt fails; the same code path as invalid credentials applies (JSON 401, inline error). |
| **EC-04** | Missing session on protected route | `/welcome` (or any future protected route) returns a redirect to `/login`. |
| **EC-05** | Corrupted/invalid session cookie | Starlette's `SessionMiddleware` rejects the unsigned/unsigned-with-wrong-key cookie; the session is treated as empty; protected routes redirect to `/login`. The user simply appears to be logged out. |
| **EC-06** | Missing template file | Server fails to read `dashboard.html`, `login.html`, or `signup.html` from disk → a 500-level error is raised. The application does not gracefully degrade. |
| **EC-07** | Missing database file | SQLite creates `vulnerable_app.db` on first connection; `init_db()` then creates the `users` table. The application starts cleanly. |
| **EC-08** | Application restart | The DB file persists. All previously created users remain. The session secret and middleware config are re-read from the source; the session secret is unchanged (deliberately). Active sessions signed with the same secret remain valid; sessions from a previous secret are invalidated. |

---

## 13. Business Rules

These are rules **derived from the implementation**, not from product intent:

1. **Authentication depends on session presence, not on database state.** A request with a valid session cookie is treated as authenticated even if the underlying user record has been deleted (or never existed, given the weak secret). The dashboard renders whatever `username` is in the session.
2. **The dashboard requires runtime substitution.** It is not rendered through a templating engine. Changing the placeholder name from `{{username}}` would require a code change to the `str.replace` call.
3. **User records are immutable after creation.** No update, delete, or recovery flow exists in the application code.
4. **Login and registration use different response formats.** Signup returns a `RedirectResponse` (standard form POST). Login returns a `JSONResponse` consumed by client-side `fetch()`. Implementations must not unify these.
5. **Template updates are visible without restart.** Because templates are read from disk per request, editing `login.html` (or any other template) on disk and refreshing the browser is sufficient to see the change. No application restart is needed.
6. **DB constraint enforcement is the primary uniqueness mechanism.** Username uniqueness is not enforced in application code; it is the `UNIQUE` column constraint on `users.username` that prevents duplicates. The application catches the resulting `IntegrityError` and surfaces it as an error message.

---

## 14. Rebuild Requirements

A compatible implementation **must** reproduce the following behaviors. Each item is testable.

1. Boots a FastAPI app on `0.0.0.0:3001` (port configurable via `PORT` env var).
2. Auto-creates `vulnerable_app.db` and the `users` table on startup.
3. Serves CSS at `/static/css/*` and images at `/static/images/*` from disk.
4. Reads HTML templates from disk on every request; no in-memory cache.
5. Mounts Starlette `SessionMiddleware` with the hardcoded weak secret (see TDD §3.1.1).
6. Implements the 8 routes listed in TDD §3.1.2 with the exact response shapes in §6 of this document.
7. Uses string concatenation (not parameter binding) for all SQL queries in `auth_service.py` and `auth.py` — this is intentional (see PRD §3.2 VULN-1, VULN-3).
8. Hashes passwords with MD5, no salt (see PRD §3.2 VULN-5).
9. Performs dashboard username injection via `str.replace('{{username}}', ...)` (see PRD §3.2 VULN-2).
10. Serves `vulnerable_app.db` via `/download/db` with no authentication (see PRD §3.2 VULN-6).
11. Applies no rate limiting on any endpoint (see PRD §3.2 VULN-7).
12. Validates no CSRF token on any form submission (see PRD §3.2 VULN-8).
13. Renders the visual design per §5 of this document — all colors, typography, spacing, shadows, layout, and responsive behavior.

---

## 15. Acceptance Criteria

| ID | Criterion |
|----|-----------|
| **AC-01** | **Registration:** submitting a new username with matching password/confirm creates a user record and redirects to `/login`. |
| **AC-02** | **Login:** submitting valid credentials via the login form results in a session being set, a redirect to `/welcome`, and the dashboard rendering the logged-in username in the hero banner. |
| **AC-03** | **Dashboard:** an unauthenticated request to `/welcome` is redirected to `/login`; an authenticated request returns the dashboard HTML with the username substituted. |
| **AC-04** | **Logout:** clicking logout clears the session; the next `/welcome` request is redirected to `/login`. |
| **AC-05** | **Search:** `GET /search?q=<text>` returns an HTML list of matching users (username + email); the response reflects the query value in its body. |
| **AC-06** | **Persistence:** user records created via signup survive a full process restart. |

---

## 16. Test Cases

| ID | Scenario | Steps | Expected Result |
|----|----------|-------|-----------------|
| **TC-01** | Signup with new username | POST `/signup` with `username=alice`, `email=a@b.com`, `password=p1`, `confirm_password=p1` | 302 to `/login`; user record exists in `vulnerable_app.db` with `username='alice'`. |
| **TC-02** | Signup with mismatched password | POST `/signup` with `password=p1`, `confirm_password=p2` (client-side JS prevents submit) | Form is not submitted; inline red error appears below confirm field. |
| **TC-03** | Signup with existing username | POST `/signup` with an already-taken username | HTML error response; no new user created. |
| **TC-04** | Login with valid credentials | POST `/login` with valid username/password via `fetch` | HTTP 200 JSON `{"success": true, "redirect": "/welcome"}`; session cookie set. |
| **TC-05** | Login with invalid password | POST `/login` with valid username and wrong password | HTTP 401 JSON `{"success": false, "error": "Invalid credentials"}`; inline error shown by client JS; no page reload. |
| **TC-06** | Login with empty fields | POST `/login` with empty username or password | Treated as invalid credentials; same response as TC-05. |
| **TC-07** | Dashboard with valid session | GET `/welcome` with a valid session cookie | Dashboard HTML returned with `{{username}}` replaced by the session's username. |
| **TC-08** | Dashboard without session | GET `/welcome` with no session cookie | 302 redirect to `/login`. |
| **TC-09** | Dashboard with corrupted session | GET `/welcome` with a tampered session cookie | Treated as no session; 302 redirect to `/login`. |
| **TC-10** | Logout flow | GET `/logout` while authenticated | Session cleared; 302 redirect to `/login`; subsequent `/welcome` request redirected to `/login`. |
| **TC-11** | Search with valid query | GET `/search?q=ali` | HTML list of matching users (e.g. `<li>alice (...)</li>`). |
| **TC-12** | Search with empty query | GET `/search` (no `q`) or `?q=` | Error string in response body. |
| **TC-13** | Static asset serving | GET `/static/css/styles.css` | CSS file served. |
| **TC-14** | Database download (no auth) | GET `/download/db` without any session | `vulnerable_app.db` file served as a download. |
| **TC-15** | Restart persistence | Create user, restart the app, attempt login with same credentials | Login succeeds; user record still present. |

---

## 17. Documentation Gaps

The following discrepancies exist between the documentation (PRD, TDD) and the implementation reality that an implementer must be aware of:

1. **The TDD describes a `backend/app/...` package layout with a separate `backend/pyproject.toml` (hatchling build system, `pytest` as dev dep).** The actual environment is a flat `uv` project at the repo root — `pyproject.toml` and `uv.lock` are at the root, not in `backend/`. The dependency set (FastAPI, Uvicorn, itsdangerous, python-multipart) is already declared at the root. A new `backend/pyproject.toml` would conflict with the existing one. Implementers must choose: (a) collapse to a flat layout and update the TDD, (b) move root dependencies into a new `backend/pyproject.toml`, or (c) accept the spec/impl drift and proceed.

2. **The TDD's stated port (3001) and the `PORT` env var override are not yet wired up in any existing code** — there is no `main.py` to inspect. The runtime default must be confirmed against the actual entry-point file once written.

3. **The TDD references logo files at `frontend/static/images/PUCIT_Logo.png`, `blue-logo-scl2.png`, and `excaliat-logo.png` (54×54px in the header).** These exist in the repository but exact dimensions and crop may differ from spec. The visual design §5.2 mandates 54×54px display, which CSS can enforce regardless of source asset size, but if source assets are absent or differently sized, the header may render with broken or oversized images until corrected.

4. **The PRD §11.1 lists FastAPI `≥0.109.0` and Uvicorn `≥0.27.0` as minimums.** The currently installed versions in `uv.lock` (FastAPI 0.139.0, Uvicorn 0.50.2) exceed these minimums. No incompatibility is expected, but a strict pin or older version in CI could surface subtle behavior differences (e.g. middleware ordering, `Form()` parsing). The implementation spec is silent on a version floor — implementers should reproduce against whatever `uv` resolves.

---

**End of Implementation Addendum**
