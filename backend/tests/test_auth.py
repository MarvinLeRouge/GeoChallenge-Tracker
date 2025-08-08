# backend/tests/test_auth.py

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import create_access_token, verify_password
from app.core.security import create_refresh_token
from app.core.settings import settings
import datetime as dt

print(settings)
client = TestClient(app)

@pytest.fixture
def test_user():
    return {
        "email": settings.admin_email,
        "username": settings.admin_username,
        "password": settings.admin_password
    }

def test_login_with_email(test_user):
    response = client.post("/auth/login", json={
        "identifier": test_user["email"],
        "password": test_user["password"]
    })
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"

def test_login_with_username(test_user):
    response = client.post("/auth/login", json={
        "identifier": test_user["username"],
        "password": test_user["password"]
    })
    assert response.status_code == 200
    assert "access_token" in response.json()

def test_login_invalid_password(test_user):
    response = client.post("/auth/login", json={
        "identifier": test_user["email"],
        "password": "wrongpass"
    })
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"

TEST_USER_ID = "689122a87dee39e7bd37945f"

def test_refresh_token_valid():
    refresh_token = create_refresh_token(
        data={"sub": TEST_USER_ID},
        expires_delta=dt.timedelta(days=7)
    )

    response = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"

def test_refresh_token_invalid_signature():
    fake_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abc.def"
    response = client.post("/auth/refresh", json={"refresh_token": fake_token})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid refresh token"

def test_refresh_token_expired():
    expired_token = create_refresh_token(
        data={"sub": TEST_USER_ID},
        expires_delta=dt.timedelta(seconds=-1)  # Déjà expiré
    )
    response = client.post("/auth/refresh", json={"refresh_token": expired_token})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid refresh token"
