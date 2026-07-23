from src.db.models.user import UserRole
from src.db.models.telegram_admin import TelegramAdmin
from tests.conftest import make_token, make_user


def make_telegram_admin(session, admin_user, telegram_id="999999"):
    ta = TelegramAdmin(user_id=admin_user.id, telegram_id=telegram_id)
    session.add(ta)
    session.commit()
    session.refresh(ta)
    return ta


def create_product(client, admin_token, name="Spiral Binding", price=1.0):
    response = client.post(
        "/api/products",
        json={"name": name, "price": price},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201
    return response.json()


def purchase(client, user_token, product_id, quantity=1, message=None):
    response = client.post(
        f"/api/products/{product_id}/purchase",
        json={"quantity": quantity, "message": message},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 201
    return response.json()


def test_non_admin_cannot_resolve_purchase(client, session):
    admin = make_user(session, role=UserRole.ADMIN)
    admin_token = make_token(admin.id)
    user = make_user(session, balance=5.0)
    user_token = make_token(user.id)
    other_user_token = make_token(make_user(session).id)

    product = create_product(client, admin_token)
    p = purchase(client, user_token, product["id"])

    response = client.patch(
        f"/api/products/purchases/{p['id']}",
        json={"action": "fulfill"},
        headers={"Authorization": f"Bearer {other_user_token}"},
    )
    assert response.status_code == 403


def test_pending_purchase_appears_in_admin_queue_and_own_history(client, session):
    admin = make_user(session, role=UserRole.ADMIN)
    admin_token = make_token(admin.id)
    user = make_user(session, balance=5.0)
    user_token = make_token(user.id)

    product = create_product(client, admin_token)
    p = purchase(client, user_token, product["id"], message="Need it by Friday")

    pending = client.get(
        "/api/products/purchases/pending", headers={"Authorization": f"Bearer {admin_token}"}
    ).json()
    assert any(row["id"] == p["id"] for row in pending)

    mine = client.get(
        "/api/products/purchases/me", headers={"Authorization": f"Bearer {user_token}"}
    ).json()
    assert any(row["id"] == p["id"] for row in mine)


def test_rejecting_purchase_refunds_balance_with_admin_message(client, session):
    admin = make_user(session, role=UserRole.ADMIN)
    admin_token = make_token(admin.id)
    user = make_user(session, balance=5.0)
    user_token = make_token(user.id)

    product = create_product(client, admin_token, price=2.0)
    p = purchase(client, user_token, product["id"])

    session.refresh(user)
    assert user.balance == 3.0

    response = client.patch(
        f"/api/products/purchases/{p['id']}",
        json={"action": "reject", "admin_message": "Out of stock, sorry!"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "rejected"
    assert body["admin_message"] == "Out of stock, sorry!"
    assert body["resolved_by_username"] == admin.username

    session.refresh(user)
    assert user.balance == 5.0

    from sqlmodel import select
    from src.db.models.transaction import Transaction, TransactionType
    refund_tx = session.exec(
        select(Transaction).where(Transaction.type == TransactionType.REFUND)
    ).first()
    assert refund_tx is not None
    assert refund_tx.amount == 2.0
    assert str(refund_tx.related_product_purchase_id) == p["id"]


def test_cannot_resolve_purchase_twice(client, session):
    admin = make_user(session, role=UserRole.ADMIN)
    admin_token = make_token(admin.id)
    user = make_user(session, balance=5.0)
    user_token = make_token(user.id)

    product = create_product(client, admin_token)
    p = purchase(client, user_token, product["id"])

    first = client.patch(
        f"/api/products/purchases/{p['id']}",
        json={"action": "fulfill"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert first.status_code == 200

    second = client.patch(
        f"/api/products/purchases/{p['id']}",
        json={"action": "reject"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert second.status_code == 409

    # Definitely not double-refunded/double-charged.
    session.refresh(user)
    assert user.balance == 4.0


def test_resolve_via_bot_secret_path_matches_web_and_returns_notifications(client, session):
    """The Telegram-side route (bot-secret gated) must resolve through the
    exact same shared manager as the web route, and hand back every
    notification the bot needs to edit (unlike a recharge request, a
    purchase is broadcast to every admin, not just one)."""
    admin = make_user(session, role=UserRole.ADMIN, balance=0.0)
    make_telegram_admin(session, admin, telegram_id="42")
    user = make_user(session, balance=5.0)
    user_token = make_token(user.id)
    admin_for_product_token = make_token(admin.id)

    product = create_product(client, admin_for_product_token, price=2.0)
    p = purchase(client, user_token, product["id"])

    import src.core.config as config_module
    telegram_secret = config_module.settings.TELEGRAM_SECRET

    resolve_response = client.patch(
        f"/api/telegram/product-purchases/{p['id']}",
        json={"chat_id": "42", "action": "reject"},
        headers={"X-Telegram-Secret": telegram_secret},
    )
    assert resolve_response.status_code == 200
    body = resolve_response.json()
    assert body["purchase"]["status"] == "rejected"
    assert isinstance(body["notifications"], list)

    session.refresh(user)
    assert user.balance == 5.0


def test_get_all_purchases_includes_every_status_newest_first(client, session):
    admin = make_user(session, role=UserRole.ADMIN)
    admin_token = make_token(admin.id)
    user = make_user(session, balance=20.0)
    user_token = make_token(user.id)

    product = create_product(client, admin_token, price=1.0)

    pending_id = purchase(client, user_token, product["id"])["id"]
    fulfilled_id = purchase(client, user_token, product["id"])["id"]
    rejected_id = purchase(client, user_token, product["id"])["id"]

    client.patch(
        f"/api/products/purchases/{fulfilled_id}",
        json={"action": "fulfill"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    client.patch(
        f"/api/products/purchases/{rejected_id}",
        json={"action": "reject"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    response = client.get(
        "/api/products/purchases", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    body = response.json()
    ids = [r["id"] for r in body]
    assert set(ids) == {pending_id, fulfilled_id, rejected_id}

    # newest-first: rejected was created last, pending first
    assert ids.index(rejected_id) < ids.index(fulfilled_id) < ids.index(pending_id)

    statuses = {r["id"]: r["status"] for r in body}
    assert statuses[pending_id] == "pending"
    assert statuses[fulfilled_id] == "fulfilled"
    assert statuses[rejected_id] == "rejected"


def test_get_all_purchases_requires_admin(client, session):
    user = make_user(session)
    user_token = make_token(user.id)

    response = client.get(
        "/api/products/purchases", headers={"Authorization": f"Bearer {user_token}"}
    )
    assert response.status_code == 403
