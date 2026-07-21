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


def test_adjust_stock_records_notes(client, session):
    admin = make_user(session, role=UserRole.ADMIN)
    token = make_token(admin.id)
    item = create_paper_item(client, token)

    response = client.post(
        f"/api/inventory/{item['id']}/adjust",
        json={"delta": -10, "reason": "manual_adjustment", "notes": "damaged box in storage"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200

    movements = client.get(
        f"/api/inventory/{item['id']}/movements",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert movements.json()[0]["notes"] == "damaged box in storage"


def test_restock_only_moves_stock_and_creates_no_expense(client, session):
    """Restock and expense-logging are deliberately decoupled — the
    purchase is normally logged separately, days before the package
    arrives."""
    admin = make_user(session, role=UserRole.ADMIN)
    token = make_token(admin.id)
    item = create_paper_item(client, token, initial_stock=50, threshold=100)

    response = client.post(
        f"/api/inventory/{item['id']}/restock",
        json={"quantity": 500},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["current_stock"] == 550.0
    assert body["is_low_stock"] is False

    expenses = client.get("/api/expenses", headers={"Authorization": f"Bearer {token}"})
    assert expenses.json() == []

    movements = client.get(
        f"/api/inventory/{item['id']}/movements",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert movements.json()[0]["reason"] == "purchase"
    assert movements.json()[0]["related_expense_id"] is None


def test_update_item_edits_fields_and_can_deactivate(client, session):
    admin = make_user(session, role=UserRole.ADMIN)
    token = make_token(admin.id)
    item = create_paper_item(client, token)

    response = client.patch(
        f"/api/inventory/{item['id']}",
        json={"name": "Paper A3", "low_stock_threshold": 200},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Paper A3"
    assert body["low_stock_threshold"] == 200.0
    assert body["is_active"] is True

    deactivate_response = client.patch(
        f"/api/inventory/{item['id']}",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert deactivate_response.json()["is_active"] is False

    active_only = client.get(
        "/api/inventory?active_only=true", headers={"Authorization": f"Bearer {token}"}
    )
    assert active_only.json() == []

    all_items = client.get("/api/inventory", headers={"Authorization": f"Bearer {token}"})
    assert len(all_items.json()) == 1


def test_update_nonexistent_item_404s(client, session):
    admin = make_user(session, role=UserRole.ADMIN)
    token = make_token(admin.id)

    response = client.patch(
        "/api/inventory/00000000-0000-0000-0000-000000000000",
        json={"name": "Nope"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


def test_non_admin_cannot_manage_inventory(client, session):
    user = make_user(session)
    token = make_token(user.id)

    response = client.post(
        "/api/inventory",
        json={"name": "Paper", "category": "paper", "unit": "sheets", "low_stock_threshold": 10},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
