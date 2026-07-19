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


def test_purchase_debits_balance_and_appears_in_ledger(client, session):
    admin = make_user(session, role=UserRole.ADMIN)
    admin_token = make_token(admin.id)
    user = make_user(session, balance=5.0)
    user_token = make_token(user.id)

    product = create_product(client, admin_token, price=1.0)

    response = client.post(
        f"/api/products/{product['id']}/purchase",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 200
    assert response.json()["new_balance"] == 4.0

    session.refresh(user)
    assert user.balance == 4.0

    from sqlmodel import select
    from src.db.models.transaction import Transaction, TransactionType
    tx = session.exec(select(Transaction).where(Transaction.type == TransactionType.PRODUCT_PURCHASE)).first()
    assert tx is not None
    assert tx.amount == -1.0
    assert str(tx.related_product_id) == product["id"]


def test_purchase_fails_with_insufficient_balance(client, session):
    admin = make_user(session, role=UserRole.ADMIN)
    admin_token = make_token(admin.id)
    user = make_user(session, balance=0.0, credit_limit=0.0)
    user_token = make_token(user.id)

    product = create_product(client, admin_token, price=5.0)

    response = client.post(
        f"/api/products/{product['id']}/purchase",
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
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 409


def test_purchase_decrements_linked_inventory(client, session):
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

    client.post(
        f"/api/products/{product['id']}/purchase",
        headers={"Authorization": f"Bearer {user_token}"},
    )

    session.refresh(item)
    assert item.current_stock == 19.0
