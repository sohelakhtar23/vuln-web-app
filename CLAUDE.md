# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Context

This is **Vulnerable Web Application - Security Lab**, an intentionally insecure FastAPI app for hands-on OWASP Top 10 security education. Built by Arif Butt for university cybersecurity courses. The app contains 8 deliberately introduced flaws that students exploit, study, and remediate. **Never deploy to production or use on unauthorized systems** — see `docs/PRD.md` §6 for safety guidelines.

The 8 vulnerabilities are **features, not bugs**. When asked to "fix" a vulnerability, confirm the intent first — the educational value depends on them staying in place until students address them as a learning exercise.

## Common Commands

Package management uses `uv` with a project at the repo root (dependencies live in root `pyproject.toml`, not a `backend/` subdir — see "Specification Drift" below).

```powershell
# Install / sync dependencies (root pyproject.toml)
uv sync

# Run the app — `sys.path` in main.py is patched so this works from any CWD:
uv run backend/app/main.py          # from project root
# or
cd backend && python app/main.py    # from backend/

# Reset the DB: delete vulnerable_app.db at the project root; init_db() recreates it on next boot.
# Server binds 0.0.0.0:3001 by default (PORT env var overrides).
# App: http://localhost:3001
```

There is currently no test suite, linter, or CI config.

## Architecture (Big Picture)

Three-layer separation, with the app launching from `backend/app/main.py` and serving frontend assets straight from `frontend/`:

- **Presentation layer** — vanilla HTML/CSS/JS in `frontend/templates/` (login, signup, dashboard) plus `frontend/static/` (css, images). Templates are read from disk per request, not cached.
- **Application layer** — FastAPI router at `backend/app/api/routes/auth.py` delegates to service logic in `backend/app/services/auth_service.py`.
- **Data layer** — SQLite file `vulnerable_app.db` at project root, accessed via `backend/app/db/session.py` (single `users` table: id, username, email, password).

Session management uses Starlette's `SessionMiddleware` (signed cookies via `itsdangerous`). Password hashing is MD5 with no salt in `backend/app/core/security.py`.

A critical runtime detail: the login POST endpoint returns a `JSONResponse` (not a `RedirectResponse`) because the login form uses `fetch()` client-side and handles the redirect via `window.location.href`. The signup POST uses a standard form submit and returns a `RedirectResponse`. Mixing these up breaks one of the two auth flows.

## Vulnerability Map

Every one of these is **intentional**. The PRD/TDD/specs document them as required flaws:

| # | Vulnerability | OWASP | Lives in |
|---|---------------|-------|----------|
| 1 | SQL Injection (login + signup) | A03:2021 Injection | `auth_service.py` — string concat in `login()` and `signup()` |
| 2 | Stored XSS (username → dashboard) | A03:2021 Injection | `auth.py` welcome handler — `html.replace('{{username}}', ...)` with no escaping |
| 3 | Reflected XSS (search) | A03:2021 Injection | `auth.py` `/search` — `q` param interpolated into HTML |
| 4 | Session Hijacking (weak secret) | A07:2021 ID & Auth Failures | `main.py` — `SECRET_KEY = "super-secret-key-12345"` |
| 5 | Weak Password Storage (MD5, no salt) | A02:2021 Crypto Failures | `security.py:hash_password()` |
| 6 | Exposed Database (no auth) | A01:2021 Broken Access Control | `auth.py` `/download/db` — serves `vulnerable_app.db` unconditionally |
| 7 | No Rate Limiting | A07:2021 ID & Auth Failures | (global) — no middleware |
| 8 | CSRF (no token validation) | A01:2021 Broken Access Control | (global) — all POST forms |

The chain is documented in `docs/TDD.md` §4.2: SQLi → session hijack → reflected XSS for cookie theft → stored XSS for persistence → DB download → MD5 offline cracking.

## Specification Hierarchy

This project follows a spec-driven workflow. The `docs/` directory contains (read in this order):

1. **`docs/PRD.md`** — product requirements, vulnerability catalog, user stories, NFRs
2. **`docs/TDD.md`** — technical design, architecture diagrams, component responsibilities, data flow, exact vulnerability root-cause line numbers
3. **`.claude/specs/app-foundation.md`** — implementation addendum: runtime behavior, user flows, FR-01–06, visual design spec, validation rules, success/alternate paths, edge cases, acceptance criteria
4. **`.claude/specs/app-foundation-plan.md`** — phase-by-step implementation plan, no code

When making changes, treat PRD/TDD as the source of truth for *what* and *why*; treat the `.claude/specs/` files for *how* (the implementation addendum covers behaviors the PRD/TDD deliberately omit, like exact typography, runtime substitution mechanics, and edge case handling).

## Specification Drift

The PRD/TDD describe a `backend/pyproject.toml` (hatchling, with `pytest` dev dep). The actual layout uses a single root `pyproject.toml` (uv-managed) — runtime deps (`fastapi`, `uvicorn`, `itsdangerous`, `python-multipart`) are declared there, and `uv.lock` lives at the repo root. The implementation plan explicitly **skipped** creating a second `pyproject.toml` to avoid conflict; do not retroactively add one. There is no `pytest` setup and no CI; the project is verified by manual checks listed in `.claude/specs/app-foundation-plan.md` Phase 10.

## Educational Disclaimer

This codebase is published for defensive security education. Any code suggestions, refactors, or "improvements" that quietly remove a vulnerability defeat the pedagogical purpose. If a user asks to harden the app, treat it as a **teaching exercise**: keep the vulnerable code in place, add the secure variant alongside it (e.g., a new route or a feature flag), and document the difference for students.
