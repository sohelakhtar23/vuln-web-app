"""Password hashing utilities.

VULN-5 (Weak Password Storage): MD5 with no salt. INTENTIONAL — do not
"fix" this without first removing the corresponding vulnerability from
the project's catalog. The whole point of this module is to produce hashes
that are reversible via rainbow tables, so students can demonstrate offline
cracking after the database is exfiltrated via VULN-6.
"""

import hashlib


def hash_password(password: str) -> str:
    """Return the MD5 hex digest of the given plaintext password.

    No salt, no pepper, no KDF. Returns a 32-character lowercase hex string.
    """
    return hashlib.md5(password.encode("utf-8")).hexdigest()


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time-ish comparison of an MD5(plain) to a stored hash.

    Plain string equality is fine here — the vulnerability is upstream
    (in the storage algorithm), not in the timing of the comparison.
    """
    return hash_password(plain) == hashed
