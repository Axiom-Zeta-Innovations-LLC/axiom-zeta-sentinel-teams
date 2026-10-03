import hashlib
import hmac
import os

from fastapi import Header, HTTPException

from gateway.core.config import load_settings


def api_key_matches(provided: str | None, expected: str) -> bool:
    if provided is None:
        return False
    return hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))


def check_gateway_key(x_api_key: str | None) -> None:
    settings = load_settings()
    if settings.api_key is None:
        # Fail closed: an unset key must not silently open the gateway.
        if settings.allow_insecure_no_auth:
            return
        raise HTTPException(
            status_code=503,
            detail="GATEWAY_API_KEY is not configured. Set it, or set ALLOW_INSECURE_NO_AUTH=true for local development only.",
        )
    if not api_key_matches(x_api_key, settings.api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    check_gateway_key(x_api_key)


def sign_user_id(user_id: str, secret: str) -> str:
    """Signature a trusted front end sends as X-User-Signature for X-User-Id."""
    return hmac.new(secret.encode("utf-8"), user_id.encode("utf-8"), hashlib.sha256).hexdigest()


def require_user_id(
    x_user_id: str | None = Header(default=None),
    x_user_signature: str | None = Header(default=None),
) -> str:
    if x_user_id is None or not x_user_id.strip():
        raise HTTPException(status_code=401, detail="Missing X-User-Id header")
    user_id = x_user_id.strip()

    # X-User-Id is only an identity if something the caller can't forge vouches for it.
    # The gateway key alone doesn't: every key holder could claim to be any user.
    secret = os.getenv("USER_ID_SIGNING_SECRET", "")
    if secret:
        expected = sign_user_id(user_id, secret)
        if x_user_signature is None or not hmac.compare_digest(x_user_signature, expected):
            raise HTTPException(status_code=401, detail="Invalid or missing X-User-Signature")
        return user_id

    if os.getenv("ALLOW_UNSIGNED_USER_ID", "false").lower() in {"1", "true", "yes"}:
        return user_id
    raise HTTPException(
        status_code=503,
        detail="USER_ID_SIGNING_SECRET is not configured. Set it (recommended), or ALLOW_UNSIGNED_USER_ID=true if X-User-Id comes only from a trusted proxy.",
    )
