import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import HTTPException

from app.core.config import get_settings
from app.core.security import InvalidTokenError, decode_supabase_jwt
from app.api.deps import get_current_user_id


def _make_token(sub: str, aud: str = "authenticated", exp_delta: timedelta = timedelta(hours=1)) -> str:
    settings = get_settings()
    payload = {
        "sub": sub,
        "aud": aud,
        "exp": datetime.now(timezone.utc) + exp_delta,
    }
    return jwt.encode(payload, settings.supabase_jwt_secret, algorithm="HS256")


def test_decode_valid_token_returns_payload():
    user_id = str(uuid.uuid4())
    token = _make_token(user_id)

    payload = decode_supabase_jwt(token)

    assert payload["sub"] == user_id


def test_decode_expired_token_raises():
    token = _make_token(str(uuid.uuid4()), exp_delta=timedelta(hours=-1))

    with pytest.raises(InvalidTokenError):
        decode_supabase_jwt(token)


def test_decode_wrong_audience_raises():
    token = _make_token(str(uuid.uuid4()), aud="other-app")

    with pytest.raises(InvalidTokenError):
        decode_supabase_jwt(token)


def test_get_current_user_id_returns_uuid_for_valid_bearer_header():
    user_id = uuid.uuid4()
    token = _make_token(str(user_id))

    result = get_current_user_id(authorization=f"Bearer {token}")

    assert result == user_id


def test_get_current_user_id_rejects_missing_header():
    with pytest.raises(HTTPException) as exc_info:
        get_current_user_id(authorization=None)

    assert exc_info.value.status_code == 401
