"""Auth0 JWT verification dependency for FastAPI.

Set AUTH0_DOMAIN and AUTH0_AUDIENCE as environment variables.
If neither is set the dependency is a no-op (useful for local dev without Auth0).
"""
import os
import logging
from functools import lru_cache

import requests as _requests
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

log = logging.getLogger("data_portal.auth")

AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN", "")
AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE", "")

_security = HTTPBearer(auto_error=False)


@lru_cache(maxsize=1)
def _jwks() -> dict:
    """Fetch Auth0 JWKS once and cache for the process lifetime."""
    url = f"https://{AUTH0_DOMAIN}/.well-known/jwks.json"
    resp = _requests.get(url, timeout=10)
    resp.raise_for_status()
    return resp.json()


def _decode(token: str) -> dict:
    header = jwt.get_unverified_header(token)
    kid = header.get("kid")
    keys = _jwks().get("keys", [])
    key = next((k for k in keys if k.get("kid") == kid), None)
    if key is None:
        # Kid not found — JWKS may have rotated; bust cache and retry once
        _jwks.cache_clear()
        keys = _jwks().get("keys", [])
        key = next((k for k in keys if k.get("kid") == kid), None)
    if key is None:
        raise JWTError("Signing key not found in JWKS")
    return jwt.decode(
        token,
        key,
        algorithms=["RS256"],
        audience=AUTH0_AUDIENCE,
        issuer=f"https://{AUTH0_DOMAIN}/",
    )


def require_auth(
    credentials: HTTPAuthorizationCredentials = Depends(_security),
) -> dict:
    """FastAPI dependency — returns the decoded JWT payload.

    Skipped entirely when AUTH0_DOMAIN / AUTH0_AUDIENCE are not configured
    (local dev without Auth0 wired up).
    """
    if not AUTH0_DOMAIN or not AUTH0_AUDIENCE:
        return {"sub": "dev-user", "dev_mode": True}

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = _decode(credentials.credentials)
        return payload
    except JWTError as exc:
        log.warning("JWT verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
