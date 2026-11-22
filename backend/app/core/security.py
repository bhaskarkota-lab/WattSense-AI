"""
Security & Cryptographic Token Module for WattSense AI™.
Implements RFC 7519 compliant HMAC-SHA256 signed session tokens,
constant-time credential verification, and customer identifier masking.
Zero external library dependencies (uses Python standard library: hmac, hashlib, secrets).
"""
import base64
import json
import time
import hmac
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional

from fastapi import HTTPException, status
from backend.app.core.config import settings

def _b64url_encode(data: bytes) -> str:
    """Encodes bytes into URL-safe base64 string without trailing padding."""
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")

def _b64url_decode(data: str) -> bytes:
    """Decodes URL-safe base64 string with restored padding."""
    rem = len(data) % 4
    if rem > 0:
        data += "=" * (4 - rem)
    return base64.urlsafe_b64decode(data.encode("utf-8"))

def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
    secret_key: Optional[str] = None
) -> str:
    """
    Creates a compact, cryptographically signed HMAC-SHA256 session token.
    Complies with standard JWT structure: header.payload.signature
    """
    key = (secret_key or settings.SECRET_KEY).encode("utf-8")
    now = int(time.time())
    
    if expires_delta:
        expire_time = now + int(expires_delta.total_seconds())
    else:
        expire_time = now + (settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)

    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        **data,
        "iat": now,
        "exp": expire_time,
        "jti": secrets.token_hex(8)
    }

    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    
    message = f"{header_b64}.{payload_b64}".encode("utf-8")
    signature = hmac.new(key, message, hashlib.sha256).digest()
    signature_b64 = _b64url_encode(signature)

    return f"{header_b64}.{payload_b64}.{signature_b64}"

def verify_access_token(
    token: str,
    secret_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Verifies token structure, cryptographic signature, and expiration timestamp.
    Raises HTTPException(401) on invalid format, bad signature, or expiration.
    """
    if not token or not isinstance(token, str):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session token missing or malformed.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    parts = token.strip().split(".")
    if len(parts) != 3:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed session token structure.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    header_b64, payload_b64, signature_b64 = parts
    key = (secret_key or settings.SECRET_KEY).encode("utf-8")
    message = f"{header_b64}.{payload_b64}".encode("utf-8")
    expected_sig = hmac.new(key, message, hashlib.sha256).digest()
    
    try:
        actual_sig = _b64url_decode(signature_b64)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session token signature encoding.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Timing-attack safe comparison
    if not hmac.compare_digest(expected_sig, actual_sig):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session token signature.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    try:
        payload_bytes = _b64url_decode(payload_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to parse session token payload.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Check expiration
    exp = payload.get("exp")
    if exp is None or int(time.time()) > int(exp):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session token has expired. Please authenticate again.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return payload

def verify_admin_passkey(passkey: str) -> bool:
    """Constant-time comparison for administrator authentication passkey."""
    if not passkey:
        return False
    return secrets.compare_digest(passkey.strip(), settings.ADMIN_SECRET_KEY.strip())

def mask_consumer_number(num: Optional[str]) -> str:
    """
    Masks middle characters of consumer account number for privacy.
    Example: 'CONS-RES-1001' -> 'CONS-RES-•••1'
    """
    if not num:
        return "UNKNOWN"
    clean = num.strip()
    if len(clean) <= 4:
        return f"•••{clean[-1]}" if len(clean) > 1 else "••••"
    
    # If dash present, preserve prefix
    if "-" in clean:
        parts = clean.split("-")
        prefix = "-".join(parts[:-1])
        last = parts[-1]
        masked_last = f"•••{last[-1]}" if len(last) > 1 else "•••"
        return f"{prefix}-{masked_last}"
    
    return f"{clean[:3]}-••••-{clean[-2:]}"

def mask_meter_number(meter: Optional[str]) -> Optional[str]:
    """Masks meter serial number for security. Example: 'MTR-1001-A' -> 'MTR-••••-A'"""
    if not meter:
        return None
    clean = meter.strip()
    if len(clean) <= 4:
        return "••••"
    if "-" in clean:
        parts = clean.split("-")
        return f"{parts[0]}-••••-{parts[-1]}"
    return f"{clean[:3]}••••{clean[-2:]}"

def create_customer_verification_token(
    consumer_number: str,
    expires_minutes: int = 120
) -> str:
    """Creates a signed verification token for an authenticated real utility customer."""
    return create_access_token(
        data={
            "sub": consumer_number.strip().upper(),
            "scope": "customer_data_access",
            "is_verified": True
        },
        expires_delta=timedelta(minutes=expires_minutes)
    )
