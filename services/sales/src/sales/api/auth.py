"""Security and JWT token claims extraction helper for perimeter trust model."""

import base64
import json
import os
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Depends, Header, HTTPException, status


@dataclass(frozen=True)
class CurrentUser:
    customer_id: str
    roles: list[str]

    def has_role(self, role: str) -> bool:
        return role in self.roles


def get_current_user(authorization: Annotated[str | None, Header()] = None) -> CurrentUser:
    """Decodes JWT payload without signature verification (perimeter trusted by NGINX gateway)."""
    auth_required = os.environ.get("SALES_AUTH_REQUIRED", "true").lower() in ("true", "1", "yes")

    if not authorization:
        if not auth_required:
            return CurrentUser(customer_id="anonymous", roles=["ADMIN", "CLIENT"])
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization scheme",
        )

    token = parts[1]
    token_parts = token.split(".")
    if len(token_parts) < 2:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token",
        )

    try:
        payload_b64 = token_parts[1]
        padding = "=" * (4 - (len(payload_b64) % 4))
        decoded_bytes = base64.urlsafe_b64decode(payload_b64 + padding)
        payload = json.loads(decoded_bytes.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cannot decode token claims",
        ) from err

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing sub claim",
        )

    roles = []
    realm_access = payload.get("realm_access")
    if isinstance(realm_access, dict):
        raw_roles = realm_access.get("roles")
        if isinstance(raw_roles, list):
            roles = [str(r) for r in raw_roles]

    return CurrentUser(customer_id=sub, roles=roles)


def require_role(role: str) -> Any:
    def role_checker(current_user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
        if not current_user.has_role(role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation requires role {role}",
            )
        return current_user

    return role_checker
