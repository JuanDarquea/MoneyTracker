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
