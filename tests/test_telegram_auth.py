from src.core.config import settings
from src.db.models.telegram_admin import TelegramAdmin
from tests.conftest import make_user

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
