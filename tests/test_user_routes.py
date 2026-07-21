from src.db.models.user import UserRole
from tests.conftest import make_token, make_user


def test_admin_cannot_change_user_role(client, session):
    admin = make_user(session, role=UserRole.ADMIN)
    admin_token = make_token(admin.id)
    target = make_user(session)

    response = client.patch(
        f"/api/users/{target.id}",
        json={"role": "admin"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 403

    session.refresh(target)
    assert target.role == UserRole.USER


def test_admin_cannot_use_legacy_is_admin_field_to_escalate(client, session):
    admin = make_user(session, role=UserRole.ADMIN)
    admin_token = make_token(admin.id)
    target = make_user(session)

    response = client.patch(
        f"/api/users/{target.id}",
        json={"is_admin": True},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 403

    session.refresh(target)
    assert target.role == UserRole.USER


def test_super_admin_can_promote_user_to_admin_or_super_admin(client, session):
    super_admin = make_user(session, role=UserRole.SUPER_ADMIN)
    super_admin_token = make_token(super_admin.id)
    target = make_user(session)

    response = client.patch(
        f"/api/users/{target.id}",
        json={"role": "admin"},
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "admin"

    response = client.patch(
        f"/api/users/{target.id}",
        json={"role": "super_admin"},
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "super_admin"


def test_admin_can_still_edit_non_role_fields(client, session):
    admin = make_user(session, role=UserRole.ADMIN)
    admin_token = make_token(admin.id)
    target = make_user(session)

    response = client.patch(
        f"/api/users/{target.id}",
        json={"name": "Updated", "credit_limit": 5.0, "is_active": False},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Updated"
    assert body["credit_limit"] == 5.0
    assert body["is_active"] is False
