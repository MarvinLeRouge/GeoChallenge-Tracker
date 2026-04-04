# backend/app/tests.test_emailverification.py

import datetime as dt

from bson import ObjectId
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.core.utils import now
from app.db.mongodb import get_collection
from app.main import app

client = TestClient(app)


def insert_temp_user(code="testcode123", expires_in_minutes=5, verified=False):
    users_collection = get_collection("users")
    user_id = ObjectId()
    user = {
        "_id": user_id,
        "username": "verifiable_user",
        "email": "verify@example.com",
        "password_hash": hash_password("Secure123!"),
        "created_at": now(),
        "verification_code": code,
        "verification_expires_at": now() + dt.timedelta(minutes=expires_in_minutes),
        "is_verified": verified,
    }
    users_collection.insert_one(user)
    return str(user_id), code


def delete_temp_user():
    get_collection("users").delete_many({"email": "verify@example.com"})


def test_verify_email_success():
    delete_temp_user()
    user_id, code = insert_temp_user()
    print(user_id, code)

    response = client.get(f"/auth/verify-email?code={code}")
    assert response.status_code == 200
    assert response.json() == {"message": "Email verified"}

    user = get_collection("users").find_one({"_id": ObjectId(user_id)})
    assert user["is_verified"] is True
    assert "verification_code" not in user or user["verification_code"] is None
    assert "verification_expires_at" not in user or user["verification_expires_at"] is None

    delete_temp_user()


def test_verify_email_expired():
    delete_temp_user()
    _, code = insert_temp_user(expires_in_minutes=-1)  # expired

    response = client.get(f"/auth/verify-email?code={code}")
    print(response.json())

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid or expired verification code"

    delete_temp_user()


def test_verify_email_invalid_code():
    delete_temp_user()
    insert_temp_user(code="realcode")

    response = client.get("/auth/verify-email?code=fakecode")
    print(response.json())
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid or expired verification code"

    delete_temp_user()


def ___test_login_unverified_user():
    delete_temp_user()
    _, code = insert_temp_user(verified=False)

    response = client.post(
        "/auth/login", json={"identifier": "verifiable_user", "password": "Secure123!"}
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Unverified user"

    delete_temp_user()
