from src.db.models.user import UserRole
from src.db.models.telegram_admin import TelegramAdmin
from tests.conftest import make_token, make_user


def make_telegram_admin(session, admin_user, telegram_id="777777"):
    ta = TelegramAdmin(user_id=admin_user.id, telegram_id=telegram_id)
    session.add(ta)
    session.commit()
    session.refresh(ta)
    return ta


def approve_recharge_request(client, user_token, admin_token, ta, amount=10.0, method="cash"):
    create_response = client.post(
        "/api/recharge-requests",
        json={"amount": amount, "method": method, "target_telegram_admin_id": str(ta.id)},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    request_id = create_response.json()["id"]
    client.patch(
        f"/api/recharge-requests/{request_id}",
        json={"status": "approved"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )


def test_non_super_admin_cannot_view_outstanding(client, session):
    admin = make_user(session, role=UserRole.ADMIN)
    admin_token = make_token(admin.id)

    response = client.get(
        "/api/collections/outstanding",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 403


def test_outstanding_float_reflects_approved_recharges(client, session):
    super_admin = make_user(session, role=UserRole.SUPER_ADMIN)
    super_admin_token = make_token(super_admin.id)
    admin = make_user(session, role=UserRole.ADMIN)
    admin_token = make_token(admin.id)
    ta = make_telegram_admin(session, admin)
    user = make_user(session)
    user_token = make_token(user.id)

    approve_recharge_request(client, user_token, admin_token, ta, amount=15.0)
    approve_recharge_request(client, user_token, admin_token, ta, amount=5.0)

    response = client.get(
        "/api/collections/outstanding",
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["username"] == admin.username
    assert body[0]["outstanding_amount"] == 20.0


def test_collect_sweeps_outstanding_and_clears_it(client, session):
    super_admin = make_user(session, role=UserRole.SUPER_ADMIN)
    super_admin_token = make_token(super_admin.id)
    admin = make_user(session, role=UserRole.ADMIN)
    admin_token = make_token(admin.id)
    ta = make_telegram_admin(session, admin)
    user = make_user(session)
    user_token = make_token(user.id)

    approve_recharge_request(client, user_token, admin_token, ta, amount=30.0)

    collect_response = client.post(
        f"/api/collections/{admin.id}/collect",
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert collect_response.status_code == 201
    assert collect_response.json()["amount_collected"] == 30.0
    assert collect_response.json()["standard_admin_username"] == admin.username
    assert collect_response.json()["super_admin_username"] == super_admin.username

    outstanding_response = client.get(
        "/api/collections/outstanding",
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert outstanding_response.json() == []


def test_collect_with_nothing_outstanding_is_conflict(client, session):
    super_admin = make_user(session, role=UserRole.SUPER_ADMIN)
    super_admin_token = make_token(super_admin.id)
    admin = make_user(session, role=UserRole.ADMIN)

    response = client.post(
        f"/api/collections/{admin.id}/collect",
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert response.status_code == 409


def test_collection_history_lists_past_events(client, session):
    super_admin = make_user(session, role=UserRole.SUPER_ADMIN)
    super_admin_token = make_token(super_admin.id)
    admin = make_user(session, role=UserRole.ADMIN)
    admin_token = make_token(admin.id)
    ta = make_telegram_admin(session, admin)
    user = make_user(session)
    user_token = make_token(user.id)

    approve_recharge_request(client, user_token, admin_token, ta, amount=12.5)
    client.post(
        f"/api/collections/{admin.id}/collect",
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )

    history_response = client.get(
        "/api/collections",
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert history_response.status_code == 200
    assert len(history_response.json()) == 1
    assert history_response.json()[0]["amount_collected"] == 12.5
