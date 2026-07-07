"""Vulnerable Web Application — entry point.

VULN-4 (Session Hijacking): SessionMiddleware is configured with a
hardcoded weak secret key. INTENTIONAL — do not load from env, do not
randomize, do not strengthen.

VULN-7 (No Rate Limiting): no rate-limiting middleware is installed.
VULN-8 (CSRF): no CSRF middleware is installed.

Boot order matters: sys.path is patched BEFORE the first
`from app...` import so the app package resolves whether the script is
launched as `uv run backend/app/main.py` (from project root) or as
`python app/main.py` (from backend/).
"""

import os
import sys
from pathlib import Path

# sys.path bootstrap must run before any `from app...` import.
# main.py lives at backend/app/main.py, so its parent is backend/app/
# and parents[1] is backend/. We add backend/ to sys.path so the
# `app` package (which IS backend/app/) is importable.
_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

import uvicorn  # noqa: E402  (after sys.path manipulation)
from fastapi import FastAPI  # noqa: E402
from starlette.middleware.sessions import SessionMiddleware  # noqa: E402
from starlette.staticfiles import StaticFiles  # noqa: E402

from app.api.routes.auth import router as auth_router  # noqa: E402
from app.db.session import init_db  # noqa: E402

app = FastAPI(title="Vulnerable Web Application - Security Lab")

# VULN-4: Session Hijacking — hardcoded weak secret. INTENTIONAL.
app.add_middleware(
    SessionMiddleware,
    secret_key="super-secret-key-12345",
)

# Static asset mounts.
_PROJECT_ROOT = _BACKEND_DIR.parent
app.mount(
    "/static/css",
    StaticFiles(directory=str(_PROJECT_ROOT / "frontend" / "static" / "css")),
    name="static-css",
)
app.mount(
    "/static/images",
    StaticFiles(directory=str(_PROJECT_ROOT / "frontend" / "static" / "images")),
    name="static-images",
)

# Routes.
app.include_router(auth_router)

# Database initialization (idempotent: CREATE TABLE IF NOT EXISTS).
init_db()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "3001"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)
