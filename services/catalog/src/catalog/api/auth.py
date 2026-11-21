"""Authentication adapter of the management API (token-claims contract of e1-identity-access; spec
catalog/service-access).

The gateway validated the token, so the service only decodes its payload, without checking the signature or
calling the identity service. Identity and roles come only from the token in the `Authorization` header; any
other header, the query string and the body are ignored for that. The public catalog never uses this module.
"""

import base64
import binascii
import json
from typing import Annotated, Any

from fastapi import Depends, Header, HTTPException, Request, status

from catalog.application.access import PLATFORM_ROLES, AuthenticatedUser

UNAUTHORIZED_HEADERS = {"WWW-Authenticate": "Bearer"}


def _unauthorized(reason: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail=reason, headers=UNAUTHORIZED_HEADERS
    )


def _payload(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        raise _unauthorized("Malformed bearer token")
    segment = parts[1]
    try:
        decoded = json.loads(base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4)))
    except (binascii.Error, ValueError) as error:
        raise _unauthorized("The token payload cannot be decoded") from error
    if not isinstance(decoded, dict):
        raise _unauthorized("The token payload cannot be decoded")
    return decoded


def _platform_roles(payload: dict[str, Any]) -> frozenset[str]:
    """Only ADMIN, EVENT_OWNER and CLIENT from realm_access.roles; every other role or claim is ignored."""
    realm_access = payload.get("realm_access")
    roles = realm_access.get("roles") if isinstance(realm_access, dict) else None
    if not isinstance(roles, list):
        return frozenset()
    return frozenset(role for role in roles if isinstance(role, str)) & PLATFORM_ROLES


def authenticated_user(
    request: Request, authorization: Annotated[str | None, Header()] = None
) -> AuthenticatedUser:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise _unauthorized("A bearer token is required")
    payload = _payload(token.strip())
    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub:
        raise _unauthorized("The token has no subject")
    # The request log records the accepted sub (e1-request-log, RL-06).
    request.state.user_id = sub
    return AuthenticatedUser(sub=sub, roles=_platform_roles(payload))


def event_manager(user: Annotated[AuthenticatedUser, Depends(authenticated_user)]) -> AuthenticatedUser:
    """Refuses users who are neither EVENT_OWNER nor ADMIN before the body is read, so a body claiming a role
    is never even considered (spec catalog/service-access: Forged role in the body)."""
    if not user.manages_events:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Managing events requires the EVENT_OWNER or the ADMIN role",
        )
    return user
