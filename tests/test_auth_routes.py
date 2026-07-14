from src.core.security import Security
from tests.conftest import make_user

PASSWORD = "correcthorsebattery"


def test_login_success(client, session):
    make_user(session, username="loginuser", pwd=Security.hash_password(PASSWORD))

    response = client.post(
        "/api/auth/login",
        json={"username": "loginuser", "pwd": PASSWORD},
    )

    assert response.status_code == 200
    assert "token" in response.json()


def test_login_wrong_credentials(client, session):
    make_user(session, username="loginuser2", pwd=Security.hash_password(PASSWORD))

    response = client.post(
        "/api/auth/login",
        json={"username": "loginuser2", "pwd": "wrongpassword"},
    )

    assert response.status_code == 404


def test_login_rate_limited_after_five_attempts(client, session):
    make_user(session, username="loginuser3", pwd=Security.hash_password(PASSWORD))

    responses = [
        client.post(
            "/api/auth/login",
            json={"username": "loginuser3", "pwd": "wrongpassword"},
        )
        for _ in range(6)
    ]

    assert [r.status_code for r in responses[:5]] == [404] * 5
    assert responses[5].status_code == 429
