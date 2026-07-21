from src.db.models.user import UserRole
from tests.conftest import make_token, make_user


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


def resolve_purchase(client, admin_token, purchase_id, action, admin_message=None):
    response = client.patch(
        f"/api/products/purchases/{purchase_id}",
        json={"action": action, "admin_message": admin_message},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    return response.json()


def get_activity_log(client, admin_token):
    response = client.get(
        "/api/settings/activity-log",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    return response.json()


def test_pending_purchase_not_in_activity_log(client, session):
    admin = make_user(session, role=UserRole.ADMIN)
    admin_token = make_token(admin.id)
    user = make_user(session, balance=5.0)
    user_token = make_token(user.id)

    product = create_product(client, admin_token)
    purchase(client, user_token, product["id"], quantity=2)

    log = get_activity_log(client, admin_token)
    assert not any(e["action"].startswith("purchase") for e in log)


def test_fulfilled_purchase_appears_in_activity_log(client, session):
    admin = make_user(session, role=UserRole.ADMIN)
    admin_token = make_token(admin.id)
    user = make_user(session, balance=5.0)
    user_token = make_token(user.id)

    product = create_product(client, admin_token, name="Spiral Binding")
    p = purchase(client, user_token, product["id"], quantity=2)
    resolve_purchase(client, admin_token, p["id"], "fulfill")

    log = get_activity_log(client, admin_token)
    entry = next(e for e in log if e["action"] == "purchase_fulfilled")
    assert entry["target_username"] == user.username
    assert entry["admin_username"] == admin.username
    assert "2x Spiral Binding" in entry["note"]


def test_rejected_purchase_appears_in_activity_log_with_admin_message(client, session):
    admin = make_user(session, role=UserRole.ADMIN)
    admin_token = make_token(admin.id)
    user = make_user(session, balance=5.0)
    user_token = make_token(user.id)

    product = create_product(client, admin_token, name="Spiral Binding")
    p = purchase(client, user_token, product["id"], quantity=1)
    resolve_purchase(client, admin_token, p["id"], "reject", admin_message="Out of stock")

    log = get_activity_log(client, admin_token)
    entry = next(e for e in log if e["action"] == "purchase_rejected")
    assert entry["target_username"] == user.username
    assert "1x Spiral Binding" in entry["note"]
    assert "Out of stock" in entry["note"]
