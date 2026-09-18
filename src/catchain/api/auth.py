"""Minimal actor identity boundary for the local review API."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from fastapi import Header, HTTPException, status


class ActorRole(StrEnum):
    REVIEWER = "reviewer"
    LEAD = "lead"
    ADMIN = "admin"


def require_actor(
    x_actor: Annotated[str | None, Header()] = None,
    x_actor_role: Annotated[ActorRole | None, Header()] = None,
) -> tuple[str, ActorRole]:
    if not x_actor or x_actor_role is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="actor required")
    return x_actor, x_actor_role

