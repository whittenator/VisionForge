from __future__ import annotations

import os

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.deps import get_current_user, get_db
from app.models.user import User
from app.models.workspace import Membership, Role

ROLE_ORDER: dict[Role, int] = {
    Role.VIEWER: 0,
    Role.ANNOTATOR: 1,
    Role.DEVELOPER: 2,
    Role.ADMIN: 3,
    Role.OWNER: 4,
}


def require_role(min_role: Role):
    """FastAPI dependency factory. Returns the current user if they meet the minimum role.

    Usage::

        @router.get("/sensitive")
        def sensitive(user: User = Depends(require_role(Role.DEVELOPER))):
            ...
    """

    def dependency(
        workspace_id: str,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        # Superusers bypass all role checks
        superuser_email = os.getenv("FIRST_SUPERUSER_EMAIL") or os.getenv("SUPERUSER_EMAIL")
        if superuser_email and current_user.email == superuser_email:
            return current_user

        membership = db.scalar(
            select(Membership).where(
                Membership.user_id == current_user.id,
                Membership.workspace_id == workspace_id,
            )
        )
        if membership is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not a member of this workspace",
            )

        user_level = ROLE_ORDER.get(membership.role, -1)
        required_level = ROLE_ORDER.get(min_role, 0)
        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires at least {min_role.value} role",
            )

        return current_user

    return dependency
