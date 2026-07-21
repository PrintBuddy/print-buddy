from src.db.models.user import UserRole
from tests.conftest import make_token, make_user


def test_create_telegram_admin_with_payment_info(client, session):
    super_admin = make_user(session, role=UserRole.SUPER_ADMIN)
    admin_token = make_token(super_admin.id)
    admin_user = make_user(session, role=UserRole.ADMIN)

    response = client.post(
        "/api/settings/telegram-admins",
        json={
            "username": admin_user.username,
            "telegram_id": "555111",
            "phone_number": "+34 600 111 222",
            "accepts_transfer": True,
            "bank_name": "Test Bank",
            "bank_iban": "ES00 0000 0000 0000",
            "bank_link": "https://example.test/pay",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["phone_number"] == "+34 600 111 222"
    assert body["accepts_transfer"] is True
    assert body["bank_iban"] == "ES00 0000 0000 0000"


def test_new_admin_defaults_to_cash_only(client, session):
    super_admin = make_user(session, role=UserRole.SUPER_ADMIN)
    admin_token = make_token(super_admin.id)
    admin_user = make_user(session, role=UserRole.ADMIN)

    response = client.post(
        "/api/settings/telegram-admins",
        json={"username": admin_user.username, "telegram_id": "555222"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["accepts_transfer"] is False
    assert body["bank_iban"] is None


def test_update_telegram_admin_payment_info(client, session):
    super_admin = make_user(session, role=UserRole.SUPER_ADMIN)
    admin_token = make_token(super_admin.id)
    admin_user = make_user(session, role=UserRole.ADMIN)

    created = client.post(
        "/api/settings/telegram-admins",
        json={"username": admin_user.username, "telegram_id": "555333"},
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()

    response = client.patch(
        f"/api/settings/telegram-admins/{created['id']}",
        json={"phone_number": "+34 611 222 333", "accepts_transfer": True, "bank_iban": "ES11 1111"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["phone_number"] == "+34 611 222 333"
    assert body["accepts_transfer"] is True
    assert body["bank_iban"] == "ES11 1111"


def test_update_nonexistent_telegram_admin_404s(client, session):
    super_admin = make_user(session, role=UserRole.SUPER_ADMIN)
    admin_token = make_token(super_admin.id)

    response = client.patch(
        "/api/settings/telegram-admins/00000000-0000-0000-0000-000000000000",
        json={"phone_number": "+34 000 000 000"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 404


def test_eligible_admins_endpoint_exposes_payment_info(client, session):
    admin = make_user(session, role=UserRole.ADMIN)
    admin_token = make_token(admin.id)
    user = make_user(session)
    user_token = make_token(user.id)

    client.post(
        "/api/settings/telegram-admins",
        json={
            "username": admin.username,
            "telegram_id": "555444",
            "phone_number": "+34 622 333 444",
            "accepts_transfer": True,
            "bank_name": "Test Bank",
            "bank_iban": "ES22 2222",
            "bank_link": "https://example.test/pay",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    response = client.get("/api/recharge-requests/admins", headers={"Authorization": f"Bearer {user_token}"})
    assert response.status_code == 200
    entries = response.json()
    assert len(entries) == 1
    assert entries[0]["phone_number"] == "+34 622 333 444"
    assert entries[0]["accepts_transfer"] is True
    assert entries[0]["bank_iban"] == "ES22 2222"
