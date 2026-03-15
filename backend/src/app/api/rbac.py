from __future__ import annotations

from fastapi import Depends, HTTPException, status

from app.db.deps import get_current_user
from app.models.user import User
from app.models.workspace import Role

ROLE_HIERARCHY: dict[Role, int] = {
    Role.VIEWER: 0,
    Role.ANNOTATOR: 1,
    Role.DEVELOPER: 2,
    Role.ADMIN: 3,
    Role.OWNER: 4,
}


def require_role(required_role: str):
    """FastAPI dependency factory. Usage: Depends(require_role('admin'))"""

    def _dep(current_user: User = Depends(get_current_user)) -> User:
        # For now we do a simple check; workspace-scoped role check can be added later.
        # This just ensures the user is authenticated.
        return current_user

    return _dep
