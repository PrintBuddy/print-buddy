from src.db.models.user import UserRole
from tests.conftest import make_token, make_user


def test_non_admin_cannot_create_expense(client, session):
    user = make_user(session)
    token = make_token(user.id)

    response = client.post(
        "/api/expenses",
        json={"category": "toner", "amount": 20.0, "description": "test"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_create_expense_appears_in_list_and_transaction_timeline(client, session):
    admin = make_user(session, role=UserRole.ADMIN)
    token = make_token(admin.id)

    response = client.post(
        "/api/expenses",
        json={"category": "toner", "amount": 45.5, "description": "New toner cartridge"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["category"] == "toner"
    assert body["amount"] == 45.5
    assert body["recorded_by_admin_id"] == str(admin.id)

    list_response = client.get(
        "/api/expenses",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    # It also appears in the unified admin transaction timeline as a
    # negative-amount EXPENSE row not tied to any user.
    from sqlmodel import select
    from src.db.models.transaction import Transaction, TransactionType
    tx = session.exec(select(Transaction).where(Transaction.type == TransactionType.EXPENSE)).first()
    assert tx is not None
    assert tx.amount == -45.5
    assert tx.user_id is None
    assert str(tx.related_expense_id) == body["id"]


def test_get_missing_expense_is_404(client, session):
    admin = make_user(session, role=UserRole.ADMIN)
    token = make_token(admin.id)
    import uuid
    response = client.get(
        f"/api/expenses/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
