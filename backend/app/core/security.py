import jwt

from app.core.config import get_settings


class InvalidTokenError(Exception):
    pass


def decode_supabase_jwt(token: str) -> dict:
    settings = get_settings()
    try:
        return jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience=settings.supabase_jwt_aud,
        )
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc
