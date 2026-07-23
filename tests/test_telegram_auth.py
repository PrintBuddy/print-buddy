from src.core.config import settings
from src.db.models.telegram_admin import TelegramAdmin
from src.db.models.user import UserRole
from tests.conftest import make_user, make_token

SECRET_HEADER = "X-Telegram-Secret"


def make_telegram_admin(session, user, chat_id="12345"):
    ta = TelegramAdmin(user_id=user.id, telegram_id=chat_id)
    session.add(ta)
    session.commit()
    session.refresh(ta)
    return ta


def test_missing_secret_rejected(client, session):
    response = client.patch(
        "/api/telegram/balance-adjust",
        json={"chat_id": "12345", "username": "someone", "amount": 10},
    )
    assert response.status_code == 403


def test_wrong_secret_rejected(client, session):
    response = client.patch(
        "/api/telegram/balance-adjust",
        json={"chat_id": "12345", "username": "someone", "amount": 10},
        headers={SECRET_HEADER: "wrong-secret"},
    )
    assert response.status_code == 403


def test_correct_secret_unregistered_chat_id_rejected(client, session):
    response = client.patch(
        "/api/telegram/balance-adjust",
        json={"chat_id": "unregistered-chat-id", "username": "someone", "amount": 10},
        headers={SECRET_HEADER: settings.TELEGRAM_SECRET},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Telegram ID not allowed"


def test_correct_secret_registered_admin_succeeds(client, session):
    telegram_admin_user = make_user(session)
    make_telegram_admin(session, telegram_admin_user, chat_id="12345")

    target_user = make_user(session, balance=0.0, credit_limit=100.0)

    response = client.patch(
        "/api/telegram/balance-adjust",
        json={"chat_id": "12345", "username": target_user.username, "amount": 10},
        headers={SECRET_HEADER: settings.TELEGRAM_SECRET},
    )

    assert response.status_code == 200
    assert response.json()["balance"] == 10.0


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


def test_get_inventory_rejects_unregistered_chat_id(client, session):
    response = client.request(
        "GET",
        "/api/telegram/inventory",
        json={"chat_id": "unregistered-chat-id"},
        headers={SECRET_HEADER: settings.TELEGRAM_SECRET},
    )
    assert response.status_code == 403


def test_get_inventory_lists_items_for_admin(client, session):
    web_admin = make_user(session, role=UserRole.ADMIN)
    web_token = make_token(web_admin.id)
    create_paper_item(client, web_token)

    telegram_admin_user = make_user(session)
    make_telegram_admin(session, telegram_admin_user, chat_id="12345")

    response = client.request(
        "GET",
        "/api/telegram/inventory",
        json={"chat_id": "12345"},
        headers={SECRET_HEADER: settings.TELEGRAM_SECRET},
    )
    assert response.status_code == 200
    names = [item["name"] for item in response.json()]
    assert "Paper A4" in names


def test_stock_adjust_by_name_updates_stock(client, session):
    web_admin = make_user(session, role=UserRole.ADMIN)
    web_token = make_token(web_admin.id)
    create_paper_item(client, web_token, initial_stock=100)

    telegram_admin_user = make_user(session)
    make_telegram_admin(session, telegram_admin_user, chat_id="12345")

    response = client.patch(
        "/api/telegram/stock-adjust",
        json={"chat_id": "12345", "item_name": "paper a4", "delta": -30},
        headers={SECRET_HEADER: settings.TELEGRAM_SECRET},
    )
    assert response.status_code == 200
    assert response.json()["current_stock"] == 70.0

    movements = client.get(
        "/api/inventory/{}/movements".format(response.json()["id"]),
        headers={"Authorization": f"Bearer {web_token}"},
    )
    assert movements.json()[0]["reason"] == "manual_adjustment"
    assert "Telegram" in movements.json()[0]["notes"]


def test_stock_adjust_unknown_item_404s(client, session):
    telegram_admin_user = make_user(session)
    make_telegram_admin(session, telegram_admin_user, chat_id="12345")

    response = client.patch(
        "/api/telegram/stock-adjust",
        json={"chat_id": "12345", "item_name": "Nonexistent Item", "delta": 10},
        headers={SECRET_HEADER: settings.TELEGRAM_SECRET},
    )
    assert response.status_code == 404


def test_stock_adjust_rejects_unregistered_chat_id(client, session):
    web_admin = make_user(session, role=UserRole.ADMIN)
    web_token = make_token(web_admin.id)
    create_paper_item(client, web_token)

    response = client.patch(
        "/api/telegram/stock-adjust",
        json={"chat_id": "unregistered-chat-id", "item_name": "Paper A4", "delta": 10},
        headers={SECRET_HEADER: settings.TELEGRAM_SECRET},
    )
    assert response.status_code == 403


def test_create_expense_from_telegram(client, session):
    telegram_admin_user = make_user(session, role=UserRole.ADMIN)
    make_telegram_admin(session, telegram_admin_user, chat_id="12345")

    response = client.post(
        "/api/telegram/expenses",
        json={"chat_id": "12345", "category": "toner", "amount": 15.5, "description": "cartridge"},
        headers={SECRET_HEADER: settings.TELEGRAM_SECRET},
    )
    assert response.status_code == 201
    assert response.json() == {"success": True}

    web_token = make_token(telegram_admin_user.id)
    expenses = client.get(
        "/api/expenses",
        headers={"Authorization": f"Bearer {web_token}"},
    ).json()
    assert len(expenses) == 1
    assert expenses[0]["category"] == "toner"
    assert expenses[0]["amount"] == 15.5
    assert expenses[0]["recorded_by_admin_id"] == str(telegram_admin_user.id)
    assert expenses[0]["paid_by_admin_id"] == str(telegram_admin_user.id)


def test_create_expense_rejects_unregistered_chat_id(client, session):
    response = client.post(
        "/api/telegram/expenses",
        json={"chat_id": "unregistered-chat-id", "category": "toner", "amount": 10},
        headers={SECRET_HEADER: settings.TELEGRAM_SECRET},
    )
    assert response.status_code == 403


def test_create_expense_rejects_invalid_category(client, session):
    telegram_admin_user = make_user(session)
    make_telegram_admin(session, telegram_admin_user, chat_id="12345")

    response = client.post(
        "/api/telegram/expenses",
        json={"chat_id": "12345", "category": "not_a_category", "amount": 10},
        headers={SECRET_HEADER: settings.TELEGRAM_SECRET},
    )
    assert response.status_code == 422
