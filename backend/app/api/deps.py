import uuid

from fastapi import Header, HTTPException, status

from app.core.security import InvalidTokenError, decode_supabase_jwt


def get_current_user_id(authorization: str | None = Header(default=None)) -> uuid.UUID:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    token = authorization.removeprefix("Bearer ")
    try:
        payload = decode_supabase_jwt(token)
    except InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token") from exc

    return uuid.UUID(payload["sub"])
