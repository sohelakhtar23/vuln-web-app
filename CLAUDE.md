# CLAUDE.md

## Project Context

This is an **intentionally vulnerable web application** for security education. It demonstrates 8 OWASP Top 10 vulnerabilities through deliberate, exploitable flaws that students can attack, understand, and remediate.

**WARNING:** All vulnerabilities are intentional. Do not "fix" them unless explicitly asked.

## Development Commands

```bash
# Install backend dependencies
cd backend && uv sync

# Run the application (from project root)
uv run backend/app/main.py

# Access at http://localhost:3001
```

## Architecture

Three-layer architecture: Presentation (HTML/CSS/JS) → Application (FastAPI) → Data (SQLite).

```
backend/app/
├── main.py              # Entry point, middleware, static mounts
├── core/security.py     # MD5 password hashing (no salt)
├── db/session.py        # SQLite connection and init
├── services/auth_service.py  # Auth business logic (SQL injection here)
└── api/routes/auth.py   # HTTP route handlers

frontend/
├── templates/           # HTML templates (loaded from disk each request)
└── static/              # CSS and images
```

## Vulnerability Map

| # | Vulnerability | File | Mechanism |
|---|---------------|------|-----------|
| 1 | SQL Injection | `backend/app/services/auth_service.py` | String concatenation in SQL queries |
| 2 | Stored XSS | `backend/app/api/routes/auth.py` | Unescaped `{{username}}` in dashboard |
| 3 | Reflected XSS | `backend/app/api/routes/auth.py` | Unescaped query param in search |
| 4 | Session Hijacking | `backend/app/main.py` | Hardcoded secret `"super-secret-key-12345"` |
| 5 | Weak Password | `backend/app/core/security.py` | MD5 without salt |
| 6 | Exposed DB | `backend/app/api/routes/auth.py` | No auth on `/download/db` |
| 7 | No Rate Limit | Global | No rate limiting middleware |
| 8 | CSRF | Global | No CSRF tokens |

## Frontend-Backend Integration

- **Login**: `fetch()` POST → JSON response → client-side redirect
- **Signup**: Standard form POST → server redirect
- **Dashboard**: Server-side `str.replace('{{username}}', ...)` — no template engine

## Important Rules

- Never use parameterized queries in `auth_service.py` or `auth.py`
- Never add CSRF tokens to forms
- Never change the session secret key
- Never add rate limiting middleware
- Keep MD5 hashing without salt in `security.py`

## Specification Hierarchy

1. `docs/PRD.md` — Product requirements
2. `docs/TDD.md` — Technical design
3. `.claude/specs/app-foundation.md` — Implementation specification
4. `.claude/specs/app-foundation-plan.md` — Implementation plan
