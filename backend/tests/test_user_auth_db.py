from app.core.security import verify_password
from app.core.settings import settings
from app.db.mongodb import get_collection

TEST_USERNAME = settings.admin_username
TEST_PASSWORD = settings.admin_password


def test_verify_user():
    users_collection = get_collection("users")
    print(users_collection)
    user = users_collection.find_one({"username": TEST_USERNAME})

    assert user is not None, "L'utilisateur n'existe pas dans la base."


def test_verify_password_valid():
    users_collection = get_collection("users")
    user = users_collection.find_one({"username": TEST_USERNAME})

    assert user is not None, "L'utilisateur n'existe pas dans la base."
    assert (
        verify_password(TEST_PASSWORD, user["password_hash"]) is True
    ), "Le mot de passe fourni ne passe pas"


def test_verify_user_password_invalid():
    users_collection = get_collection("users")
    user = users_collection.find_one({"username": TEST_USERNAME})

    assert user is not None
    assert (
        verify_password(TEST_PASSWORD + "a", user["password_hash"]) is False
    ), "le mot de passe erroné fonctionne"
