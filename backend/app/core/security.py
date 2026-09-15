from functools import lru_cache

import jwt
from jwt import PyJWKClient

from app.core.config import get_settings


class InvalidTokenError(Exception):
    pass


@lru_cache
def _jwks_client() -> PyJWKClient:
    settings = get_settings()
    jwks_url = f"{settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
    return PyJWKClient(jwks_url)


def decode_supabase_jwt(token: str) -> dict:
    settings = get_settings()
    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") == "HS256":
            # Self-issued tokens (test suite, local dev without a live Supabase
            # project) signed with the shared secret.
            return jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience=settings.supabase_jwt_aud,
            )

        # Real Supabase-issued tokens are signed with an asymmetric key
        # (ES256) verified against the project's public JWKS, not a shared
        # secret.
        signing_key = _jwks_client().get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=[header["alg"]],
            audience=settings.supabase_jwt_aud,
        )
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc
    except Exception as exc:
        # Anything else (bad JWKS URL/config, network failure reaching
        # Supabase, malformed key, etc.) should still surface to the client
        # as a clean 401 — not an unhandled 500. Starlette's error handling
        # sits outside CORSMiddleware, so an uncaught exception here comes
        # back to the browser with no CORS headers at all, which looks like
        # a CORS failure instead of the real cause.
        raise InvalidTokenError(str(exc)) from exc
