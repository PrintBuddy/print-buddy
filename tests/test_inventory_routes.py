from src.db.models.user import UserRole
from tests.conftest import make_token, make_user


def create_paper_item(client, token, initial_stock=500, threshold=100):
    response = client.post(
        "/api/inventory",
        json={
            "name": "Paper A4",
            "category": "paper",
            "unit": "sheets",
            "initial_stock": initial_stock,
            "low_stock_threshold": threshold,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    return response.json()


def test_create_and_list_item(client, session):
    admin = make_user(session, role=UserRole.ADMIN)
    token = make_token(admin.id)

    item = create_paper_item(client, token)
    assert item["current_stock"] == 500.0
    assert item["is_low_stock"] is False

    list_response = client.get("/api/inventory", headers={"Authorization": f"Bearer {token}"})
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1


def test_adjust_stock_updates_and_flags_low(client, session):
    admin = make_user(session, role=UserRole.ADMIN)
    token = make_token(admin.id)
    item = create_paper_item(client, token, initial_stock=150, threshold=100)

    response = client.post(
        f"/api/inventory/{item['id']}/adjust",
        json={"delta": -80, "reason": "manual_adjustment"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["current_stock"] == 70.0
    assert body["is_low_stock"] is True

    movements = client.get(
        f"/api/inventory/{item['id']}/movements",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert movements.status_code == 200
    assert len(movements.json()) == 1
    assert movements.json()[0]["delta"] == -80.0


def test_restock_creates_expense_and_movement_together(client, session):
    admin = make_user(session, role=UserRole.ADMIN)
    token = make_token(admin.id)
    item = create_paper_item(client, token, initial_stock=50, threshold=100)

    response = client.post(
        f"/api/inventory/{item['id']}/restock",
        json={
            "quantity": 500,
            "expense_category": "paper",
            "expense_amount": 25.0,
            "expense_description": "Bought a new box of paper",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["current_stock"] == 550.0
    assert body["is_low_stock"] is False

    expenses = client.get("/api/expenses", headers={"Authorization": f"Bearer {token}"})
    assert len(expenses.json()) == 1
    assert expenses.json()[0]["amount"] == 25.0

    movements = client.get(
        f"/api/inventory/{item['id']}/movements",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert movements.json()[0]["reason"] == "purchase"
    assert movements.json()[0]["related_expense_id"] == expenses.json()[0]["id"]


def test_non_admin_cannot_manage_inventory(client, session):
    user = make_user(session)
    token = make_token(user.id)

    response = client.post(
        "/api/inventory",
        json={"name": "Paper", "category": "paper", "unit": "sheets", "low_stock_threshold": 10},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
