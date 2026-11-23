from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.routes import auth


class FakeSession:
    def __init__(self, user: SimpleNamespace) -> None:
        self.user = user
        self.execute_called = False

    def scalar(self, _statement):
        return self.user

    def execute(self, *_args, **_kwargs):
        self.execute_called = True
        raise AssertionError("Tenant lookup must not run before MFA is completed")


def test_password_login_does_not_issue_token_for_mfa_enabled_user(monkeypatch) -> None:
    user = SimpleNamespace(
        id=uuid4(),
        email="clinician@example.test",
        is_active=True,
        mfa_enabled=True,
        password_hash="test-hash",
    )
    db = FakeSession(user)
    monkeypatch.setattr(auth, "verify_password", lambda _password, _hash: True)

    with pytest.raises(HTTPException) as exc_info:
        auth.issue_token(
            form=SimpleNamespace(username="clinician@example.test", password="correct-password"),
            hospital_id=uuid4(),
            db=db,
        )

    assert exc_info.value.status_code == 403
    assert "verification flow is not yet available" in exc_info.value.detail
    assert db.execute_called is False
