"""Unit tests for the workspace authorization gate (``api/rbac.require_role``).

This dependency is the single chokepoint for workspace RBAC, so the role
hierarchy, the non-membership rejection, and the superuser bypass each get
direct coverage. We exercise the returned ``dependency`` callable directly with
a real DB session rather than going through HTTP, which keeps the assertions
focused on the authorization logic itself.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.api.rbac import ROLE_ORDER, require_role
from app.models.user import User
from app.models.workspace import Membership, Role, Workspace
from tests.conftest import TestingSessionLocal


def _mk_user(db, *, email: str | None = None, is_superuser: bool = False) -> User:
    user = User(
        id=str(uuid.uuid4()),
        name="Tester",
        email=email or f"{uuid.uuid4().hex[:8]}@example.com",
        password_hash="x",
        is_superuser=is_superuser,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _mk_workspace(db, owner_id: str) -> Workspace:
    ws = Workspace(id=str(uuid.uuid4()), name="WS", created_by=owner_id)
    db.add(ws)
    db.commit()
    db.refresh(ws)
    return ws


def _mk_membership(db, *, user_id: str, workspace_id: str, role: Role) -> Membership:
    m = Membership(id=str(uuid.uuid4()), user_id=user_id, workspace_id=workspace_id, role=role)
    db.add(m)
    db.commit()
    return m


def test_role_order_is_monotonic():
    # The ladder must be strictly increasing viewer < … < owner for the
    # >= comparison in require_role to be meaningful.
    levels = [
        ROLE_ORDER[Role.VIEWER],
        ROLE_ORDER[Role.ANNOTATOR],
        ROLE_ORDER[Role.DEVELOPER],
        ROLE_ORDER[Role.ADMIN],
        ROLE_ORDER[Role.OWNER],
    ]
    assert levels == sorted(levels)
    assert len(set(levels)) == len(levels)


def test_member_with_sufficient_role_is_allowed():
    db = TestingSessionLocal()
    try:
        user = _mk_user(db)
        ws = _mk_workspace(db, user.id)
        _mk_membership(db, user_id=user.id, workspace_id=ws.id, role=Role.DEVELOPER)

        dep = require_role(Role.DEVELOPER)
        result = dep(workspace_id=ws.id, current_user=user, db=db)
        assert result is user
    finally:
        db.close()


def test_member_with_higher_role_is_allowed():
    db = TestingSessionLocal()
    try:
        user = _mk_user(db)
        ws = _mk_workspace(db, user.id)
        _mk_membership(db, user_id=user.id, workspace_id=ws.id, role=Role.OWNER)

        dep = require_role(Role.DEVELOPER)
        assert dep(workspace_id=ws.id, current_user=user, db=db) is user
    finally:
        db.close()


def test_member_with_insufficient_role_is_forbidden():
    db = TestingSessionLocal()
    try:
        user = _mk_user(db)
        ws = _mk_workspace(db, user.id)
        _mk_membership(db, user_id=user.id, workspace_id=ws.id, role=Role.VIEWER)

        dep = require_role(Role.DEVELOPER)
        with pytest.raises(HTTPException) as exc:
            dep(workspace_id=ws.id, current_user=user, db=db)
        assert exc.value.status_code == 403
        assert "developer" in exc.value.detail
    finally:
        db.close()


def test_non_member_is_forbidden():
    db = TestingSessionLocal()
    try:
        user = _mk_user(db)
        ws = _mk_workspace(db, user.id)
        # No membership row created for this user/workspace pair.
        dep = require_role(Role.VIEWER)
        with pytest.raises(HTTPException) as exc:
            dep(workspace_id=ws.id, current_user=user, db=db)
        assert exc.value.status_code == 403
        assert "member" in exc.value.detail.lower()
    finally:
        db.close()


def test_superuser_email_bypasses_membership_check(monkeypatch):
    db = TestingSessionLocal()
    try:
        user = _mk_user(db, email="root@example.com")
        ws = _mk_workspace(db, user.id)
        # Deliberately no membership — the bypass must still admit the user.
        monkeypatch.setenv("FIRST_SUPERUSER_EMAIL", "root@example.com")
        monkeypatch.delenv("SUPERUSER_EMAIL", raising=False)

        dep = require_role(Role.OWNER)
        assert dep(workspace_id=ws.id, current_user=user, db=db) is user
    finally:
        db.close()


def test_non_superuser_email_does_not_bypass(monkeypatch):
    db = TestingSessionLocal()
    try:
        user = _mk_user(db, email="someone@example.com")
        ws = _mk_workspace(db, user.id)
        monkeypatch.setenv("FIRST_SUPERUSER_EMAIL", "root@example.com")

        dep = require_role(Role.VIEWER)
        with pytest.raises(HTTPException) as exc:
            dep(workspace_id=ws.id, current_user=user, db=db)
        assert exc.value.status_code == 403
    finally:
        db.close()
