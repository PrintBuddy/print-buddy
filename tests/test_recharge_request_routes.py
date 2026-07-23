from src.db.models.user import UserRole
from src.db.models.telegram_admin import TelegramAdmin
from tests.conftest import make_token, make_user


def make_telegram_admin(session, admin_user, telegram_id="999999"):
    ta = TelegramAdmin(user_id=admin_user.id, telegram_id=telegram_id)
    session.add(ta)
    session.commit()
    session.refresh(ta)
    return ta


def test_create_and_list_eligible_admins(client, session):
    admin = make_user(session, role=UserRole.ADMIN)
    make_telegram_admin(session, admin)
    user = make_user(session)
    token = make_token(user.id)

    response = client.get(
        "/api/recharge-requests/admins",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["username"] == admin.username


def test_create_request_then_admin_approves_credits_balance(client, session):
    admin = make_user(session, role=UserRole.ADMIN, balance=0.0)
    ta = make_telegram_admin(session, admin)
    user = make_user(session, balance=0.0)
    user_token = make_token(user.id)
    admin_token = make_token(admin.id)

    create_response = client.post(
        "/api/recharge-requests",
        json={"amount": 20.0, "method": "cash", "target_telegram_admin_id": str(ta.id)},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert create_response.status_code == 201
    request_id = create_response.json()["id"]
    assert create_response.json()["status"] == "pending"

    pending_response = client.get(
        "/api/recharge-requests/pending",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert pending_response.status_code == 200
    assert len(pending_response.json()) == 1

    resolve_response = client.patch(
        f"/api/recharge-requests/{request_id}",
        json={"status": "approved"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resolve_response.status_code == 200
    assert resolve_response.json()["status"] == "approved"

    session.refresh(user)
    assert user.balance == 20.0

    my_requests = client.get(
        "/api/recharge-requests/me",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert my_requests.status_code == 200
    assert my_requests.json()[0]["status"] == "approved"


def test_double_resolve_is_conflict_and_does_not_double_credit(client, session):
    admin = make_user(session, role=UserRole.ADMIN, balance=0.0)
    ta = make_telegram_admin(session, admin)
    user = make_user(session, balance=0.0)
    user_token = make_token(user.id)
    admin_token = make_token(admin.id)

    create_response = client.post(
        "/api/recharge-requests",
        json={"amount": 10.0, "method": "transfer", "target_telegram_admin_id": str(ta.id)},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    request_id = create_response.json()["id"]

    first = client.patch(
        f"/api/recharge-requests/{request_id}",
        json={"status": "approved"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert first.status_code == 200

    second = client.patch(
        f"/api/recharge-requests/{request_id}",
        json={"status": "approved"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert second.status_code == 409

    session.refresh(user)
    assert user.balance == 10.0


def test_reject_does_not_credit_balance(client, session):
    admin = make_user(session, role=UserRole.ADMIN, balance=0.0)
    ta = make_telegram_admin(session, admin)
    user = make_user(session, balance=0.0)
    user_token = make_token(user.id)
    admin_token = make_token(admin.id)

    create_response = client.post(
        "/api/recharge-requests",
        json={"amount": 10.0, "method": "cash", "target_telegram_admin_id": str(ta.id)},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    request_id = create_response.json()["id"]

    resolve_response = client.patch(
        f"/api/recharge-requests/{request_id}",
        json={"status": "rejected"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resolve_response.status_code == 200
    assert resolve_response.json()["status"] == "rejected"

    session.refresh(user)
    assert user.balance == 0.0


def test_non_admin_cannot_resolve(client, session):
    admin = make_user(session, role=UserRole.ADMIN)
    ta = make_telegram_admin(session, admin)
    user = make_user(session)
    other_user = make_user(session)
    user_token = make_token(user.id)
    other_token = make_token(other_user.id)

    create_response = client.post(
        "/api/recharge-requests",
        json={"amount": 10.0, "method": "cash", "target_telegram_admin_id": str(ta.id)},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    request_id = create_response.json()["id"]

    resolve_response = client.patch(
        f"/api/recharge-requests/{request_id}",
        json={"status": "approved"},
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resolve_response.status_code == 403


def test_get_all_includes_every_status_newest_first(client, session):
    admin = make_user(session, role=UserRole.ADMIN, balance=0.0)
    ta = make_telegram_admin(session, admin)
    user = make_user(session, balance=0.0)
    user_token = make_token(user.id)
    admin_token = make_token(admin.id)

    def create(amount):
        r = client.post(
            "/api/recharge-requests",
            json={"amount": amount, "method": "cash", "target_telegram_admin_id": str(ta.id)},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        return r.json()["id"]

    pending_id = create(5.0)
    approved_id = create(10.0)
    rejected_id = create(15.0)

    client.patch(
        f"/api/recharge-requests/{approved_id}",
        json={"status": "approved"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    client.patch(
        f"/api/recharge-requests/{rejected_id}",
        json={"status": "rejected"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    response = client.get(
        "/api/recharge-requests",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    body = response.json()
    ids = [r["id"] for r in body]
    assert set(ids) == {pending_id, approved_id, rejected_id}

    # newest-first: rejected was created last, pending first
    assert ids.index(rejected_id) < ids.index(approved_id) < ids.index(pending_id)

    statuses = {r["id"]: r["status"] for r in body}
    assert statuses[pending_id] == "pending"
    assert statuses[approved_id] == "approved"
    assert statuses[rejected_id] == "rejected"


def test_get_all_requires_admin(client, session):
    user = make_user(session)
    user_token = make_token(user.id)

    response = client.get(
        "/api/recharge-requests",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 403


def test_resolve_via_bot_secret_path_also_works(client, session):
    """The Telegram-side route (bot-secret gated) must resolve through the
    exact same shared resolver as the web route."""
    admin = make_user(session, role=UserRole.ADMIN, balance=0.0)
    ta = make_telegram_admin(session, admin, telegram_id="42")
    user = make_user(session, balance=0.0)
    user_token = make_token(user.id)

    create_response = client.post(
        "/api/recharge-requests",
        json={"amount": 5.0, "method": "cash", "target_telegram_admin_id": str(ta.id)},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    request_id = create_response.json()["id"]

    import src.core.config as config_module
    telegram_secret = config_module.settings.TELEGRAM_SECRET

    resolve_response = client.patch(
        f"/api/telegram/recharge-requests/{request_id}",
        json={"chat_id": "42", "action": "approve"},
        headers={"X-Telegram-Secret": telegram_secret},
    )
    assert resolve_response.status_code == 200

    session.refresh(user)
    assert user.balance == 5.0
