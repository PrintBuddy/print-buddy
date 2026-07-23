from src.db.models.user import UserRole
from src.db.models.inventory import InventoryCategory
from src.db.crud.inventory import InventoryService
from tests.conftest import make_token, make_user


def create_product(client, admin_token, name="Spiral Binding", price=1.0):
    response = client.post(
        "/api/products",
        json={"name": name, "price": price},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201
    return response.json()


def test_non_admin_cannot_create_product(client, session):
    user = make_user(session)
    token = make_token(user.id)
    response = client.post(
        "/api/products",
        json={"name": "Spiral Binding", "price": 1.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_list_only_shows_active_products_to_regular_users(client, session):
    admin = make_user(session, role=UserRole.ADMIN)
    admin_token = make_token(admin.id)
    user = make_user(session)
    user_token = make_token(user.id)

    active_product = create_product(client, admin_token, name="Spiral Binding")
    inactive_product = create_product(client, admin_token, name="Discontinued Item")
    client.patch(
        f"/api/products/{inactive_product['id']}",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    response = client.get("/api/products", headers={"Authorization": f"Bearer {user_token}"})
    assert response.status_code == 200
    names = [p["name"] for p in response.json()]
    assert active_product["name"] in names
    assert inactive_product["name"] not in names

    admin_list = client.get("/api/products/admin", headers={"Authorization": f"Bearer {admin_token}"})
    admin_names = [p["name"] for p in admin_list.json()]
    assert active_product["name"] in admin_names
    assert inactive_product["name"] in admin_names


def test_purchase_debits_immediately_but_stays_pending(client, session):
    admin = make_user(session, role=UserRole.ADMIN)
    admin_token = make_token(admin.id)
    user = make_user(session, balance=5.0)
    user_token = make_token(user.id)

    product = create_product(client, admin_token, price=1.0)

    response = client.post(
        f"/api/products/{product['id']}/purchase",
        json={"quantity": 1, "message": "Please give me the blue one"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    assert body["total_amount"] == 1.0
    assert body["message"] == "Please give me the blue one"

    session.refresh(user)
    assert user.balance == 4.0

    from sqlmodel import select
    from src.db.models.transaction import Transaction, TransactionType
    tx = session.exec(select(Transaction).where(Transaction.type == TransactionType.PRODUCT_PURCHASE)).first()
    assert tx is not None
    assert tx.amount == -1.0
    assert str(tx.related_product_id) == product["id"]
    assert str(tx.related_product_purchase_id) == body["id"]


def test_purchase_quantity_multiplies_total(client, session):
    admin = make_user(session, role=UserRole.ADMIN)
    admin_token = make_token(admin.id)
    user = make_user(session, balance=10.0)
    user_token = make_token(user.id)

    product = create_product(client, admin_token, price=1.5)

    response = client.post(
        f"/api/products/{product['id']}/purchase",
        json={"quantity": 3},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 201
    assert response.json()["total_amount"] == 4.5

    session.refresh(user)
    assert user.balance == 5.5


def test_purchase_fails_with_insufficient_balance(client, session):
    admin = make_user(session, role=UserRole.ADMIN)
    admin_token = make_token(admin.id)
    user = make_user(session, balance=0.0, credit_limit=0.0)
    user_token = make_token(user.id)

    product = create_product(client, admin_token, price=5.0)

    response = client.post(
        f"/api/products/{product['id']}/purchase",
        json={"quantity": 1},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 402
    session.refresh(user)
    assert user.balance == 0.0


def test_purchase_fails_for_inactive_product(client, session):
    admin = make_user(session, role=UserRole.ADMIN)
    admin_token = make_token(admin.id)
    user = make_user(session, balance=10.0)
    user_token = make_token(user.id)

    product = create_product(client, admin_token, price=1.0)
    client.patch(
        f"/api/products/{product['id']}",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    response = client.post(
        f"/api/products/{product['id']}/purchase",
        json={"quantity": 1},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 409


def test_fulfilling_purchase_decrements_linked_inventory(client, session):
    admin = make_user(session, role=UserRole.ADMIN)
    admin_token = make_token(admin.id)
    user = make_user(session, balance=10.0)
    user_token = make_token(user.id)

    inventory_service = InventoryService()
    item = inventory_service.create_item(
        "Binding Coils", InventoryCategory.BINDING_SUPPLY, "coils", 2, session, initial_stock=20
    )

    product = create_product(client, admin_token, price=1.0)
    client.patch(
        f"/api/products/{product['id']}",
        json={"inventory_item_id": str(item.id)},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    purchase = client.post(
        f"/api/products/{product['id']}/purchase",
        json={"quantity": 2},
        headers={"Authorization": f"Bearer {user_token}"},
    ).json()

    # Stock shouldn't move until the admin actually hands the item over.
    session.refresh(item)
    assert item.current_stock == 20.0

    resolve_response = client.patch(
        f"/api/products/purchases/{purchase['id']}",
        json={"action": "fulfill"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resolve_response.status_code == 200
    assert resolve_response.json()["status"] == "fulfilled"

    session.refresh(item)
    assert item.current_stock == 18.0


def test_delete_product_removes_it(client, session):
    admin = make_user(session, role=UserRole.ADMIN)
    admin_token = make_token(admin.id)
    product = create_product(client, admin_token, name="Mistake Product")

    response = client.delete(
        f"/api/products/{product['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200

    admin_list = client.get("/api/products/admin", headers={"Authorization": f"Bearer {admin_token}"})
    ids = [p["id"] for p in admin_list.json()]
    assert product["id"] not in ids


def test_delete_product_preserves_purchase_history(client, session):
    admin = make_user(session, role=UserRole.ADMIN)
    admin_token = make_token(admin.id)
    user = make_user(session, balance=10.0)
    user_token = make_token(user.id)

    product = create_product(client, admin_token, name="Spiral Binding", price=2.0)
    purchase = client.post(
        f"/api/products/{product['id']}/purchase",
        json={"quantity": 1},
        headers={"Authorization": f"Bearer {user_token}"},
    ).json()

    delete_response = client.delete(
        f"/api/products/{product['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert delete_response.status_code == 200

    # The purchase's own denormalized fields survive regardless of the
    # product row disappearing — this is what actually protects history
    # (product_id itself is nulled via the FK's ondelete=SET NULL, which
    # Postgres enforces in production; the test suite's SQLite engine
    # doesn't enforce FK actions by default, so that specific nulling
    # isn't observable here).
    mine = client.get("/api/products/purchases/me", headers={"Authorization": f"Bearer {user_token}"}).json()
    match = next(p for p in mine if p["id"] == purchase["id"])
    assert match["product_name"] == "Spiral Binding"
    assert match["unit_price"] == 2.0


def test_delete_nonexistent_product_404s(client, session):
    admin = make_user(session, role=UserRole.ADMIN)
    admin_token = make_token(admin.id)

    response = client.delete(
        "/api/products/00000000-0000-0000-0000-000000000000",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 404
