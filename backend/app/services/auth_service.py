"""Authentication business logic for signup and login.

VULN-1 (SQL Injection): all SQL queries in this module are built via
string concatenation of user-controlled input. INTENTIONAL. Do not
"fix" by switching to parameterized queries without removing the
catalog entry first.

VULN-5 (Weak Password Storage): password hashing is delegated to
core.security, which uses unsalted MD5.

Response-shape contract (do not change without coordinating the
frontend templates):
- signup()  -> RedirectResponse (HTML form POST; browser follows redirect)
- login()   -> JSONResponse     (fetch() in login.html reads .success / .error)
"""

import sqlite3

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.core.security import hash_password
from app.db.session import get_db


def signup(username: str, email: str, password: str):
    """Register a new user.

    Returns a RedirectResponse to /login on success, or an HTMLResponse
    containing an error string on validation/duplicate failure.
    """
    if not username or not email or not password:
        return HTMLResponse("All fields are required", status_code=400)

    hashed = hash_password(password)

    conn = get_db()
    try:
        # VULN-1: SQL Injection via string concatenation. INTENTIONAL.
        query = (
            "INSERT INTO users (username, email, password) "
            "VALUES ('" + username + "', '" + email + "', '" + hashed + "')"
        )
        conn.execute(query)
        conn.commit()
    except sqlite3.IntegrityError:
        return HTMLResponse("Username already exists", status_code=409)
    except Exception as e:
        return HTMLResponse(f"Error: {str(e)}", status_code=500)
    finally:
        conn.close()

    return RedirectResponse(url="/login", status_code=302)


def login(request: Request, username: str, password: str):
    """Authenticate a user.

    Returns a JSONResponse on both success and failure (NOT a
    RedirectResponse) because the login form uses fetch() and reads the
    JSON body client-side.

    Success payload: {"success": true,  "redirect": "/welcome"}  (HTTP 200)
    Failure payload: {"success": false, "error": "Invalid credentials"}  (HTTP 401)
    """
    if not username or not password:
        return JSONResponse(
            {"success": False, "error": "Invalid credentials"},
            status_code=401,
        )

    hashed = hash_password(password)

    conn = get_db()
    try:
        # VULN-1: SQL Injection via string concatenation. INTENTIONAL.
        query = (
            "SELECT * FROM users WHERE username = '"
            + username
            + "' AND password = '"
            + hashed
            + "'"
        )
        row = conn.execute(query).fetchone()
    finally:
        conn.close()

    if row is None:
        return JSONResponse(
            {"success": False, "error": "Invalid credentials"},
            status_code=401,
        )

    request.session["user_id"] = row["id"]
    request.session["username"] = row["username"]
    request.session["email"] = row["email"]

    return JSONResponse(
        {"success": True, "redirect": "/welcome"},
        status_code=200,
    )
