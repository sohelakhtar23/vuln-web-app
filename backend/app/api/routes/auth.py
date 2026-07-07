"""HTTP route handlers for the Vulnerable Web Application.

This module wires the FastAPI endpoints. Most business logic lives in
app.services.auth_service — the exceptions are the static template/file
serves and the /search endpoint (which builds its own SQL by string
concatenation inline, VULN-1 + VULN-3).

Vulnerabilities living in this file:
  - VULN-2 (Stored XSS): /welcome uses str.replace on the raw dashboard
    HTML with the session username, no escaping.
  - VULN-3 (Reflected XSS): /search interpolates the q parameter into
    the HTML response without escaping.
  - VULN-6 (Exposed Database): /download/db serves vulnerable_app.db
    with no authentication check.
  - VULN-7 (No Rate Limiting): no middleware anywhere in the app.
  - VULN-8 (CSRF): no token validation on any form.
"""

from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from app.db.session import get_db
from app.services import auth_service

router = APIRouter()

# backend/app/api/routes/auth.py -> project root (4 parents up)
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
TEMPLATES_DIR = _PROJECT_ROOT / "frontend" / "templates"
DB_PATH = _PROJECT_ROOT / "vulnerable_app.db"


# ---------- Root + auth pages ----------

@router.get("/")
def index():
    """Redirect the bare host to the signup page."""
    return RedirectResponse(url="/signup", status_code=302)


@router.get("/signup")
def signup_page():
    """Serve the signup form by reading signup.html from disk."""
    html = (TEMPLATES_DIR / "signup.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


@router.post("/signup")
def signup_post(
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
):
    """Process the signup form. Returns RedirectResponse to /login on success."""
    return auth_service.signup(username=username, email=email, password=password)


@router.get("/login")
def login_page():
    """Serve the login form by reading login.html from disk."""
    html = (TEMPLATES_DIR / "login.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


@router.post("/login")
def login_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    """Process the login form. Returns JSONResponse (consumed by fetch() in login.html)."""
    return auth_service.login(request=request, username=username, password=password)


# ---------- Vulnerable endpoints ----------

@router.get("/download/db")
def download_db():
    """VULN-6: Exposed Database. No authentication check — INTENTIONAL.

    The SQLite file is served directly to anyone who hits this URL.
    """
    # VULN-6: no session check. INTENTIONAL.
    return FileResponse(str(DB_PATH), filename="vulnerable_app.db")


@router.get("/search")
def search_user(q: str = ""):
    """Search users. VULN-1 (SQLi) + VULN-3 (Reflected XSS). INTENTIONAL."""
    if not q:
        return HTMLResponse(
            "Error: query parameter 'q' is required",
            status_code=400,
        )
    try:
        conn = get_db()
        try:
            # VULN-1: SQL Injection via string concatenation. INTENTIONAL.
            query = (
                "SELECT username, email FROM users "
                "WHERE username LIKE '%" + q + "%' "
                "OR email LIKE '%" + q + "%'"
            )
            rows = conn.execute(query).fetchall()
        finally:
            conn.close()

        # VULN-3: Reflected XSS — q and the row values are interpolated
        # into the response HTML without escaping. INTENTIONAL.
        items = "".join(
            f"<li>{row['username']} ({row['email']})</li>"
            for row in rows
        )
        return HTMLResponse(
            f"<h1>Search results for: {q}</h1><ul>{items}</ul>"
        )
    except Exception as e:
        # Information disclosure: raw exception returned in body.
        return HTMLResponse(f"Error: {str(e)}", status_code=500)


# ---------- Protected page + logout ----------

@router.get("/welcome")
def welcome_page(request: Request):
    """Dashboard. Auth check + dashboard template + str.replace for username."""
    if "user_id" not in request.session:
        return RedirectResponse(url="/login", status_code=302)

    html = (TEMPLATES_DIR / "dashboard.html").read_text(encoding="utf-8")
    # VULN-2: Stored XSS — str.replace with no html.escape. INTENTIONAL.
    html = html.replace("{{username}}", request.session["username"])
    return HTMLResponse(html)


@router.get("/logout")
def logout(request: Request):
    """Clear the session and redirect to the login page."""
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)
