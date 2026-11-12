"""Tests for AppError codes in the error envelope."""

import ast
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import AppError, ErrorCode
from app.core.exception_handlers import register_exception_handlers
from app.core.security import PASSWORD_ERROR_CODES, validate_password_strength

APP_DIR = Path(__file__).resolve().parents[2] / "app"


def _http_handler():
    app = FastAPI()
    register_exception_handlers(app)
    return app.exception_handlers[StarletteHTTPException]


@pytest.mark.asyncio
async def test_app_error_code_is_returned_in_the_envelope():
    exc = AppError(404, ErrorCode.CACHE_NOT_FOUND, "Cache not found")
    response = await _http_handler()(MagicMock(), exc)
    assert response.status_code == 404
    assert json.loads(response.body)["error"] == {
        "code": "CACHE_NOT_FOUND",
        "message": "Cache not found",
    }


@pytest.mark.asyncio
async def test_plain_http_exception_keeps_the_generic_code():
    response = await _http_handler()(MagicMock(), StarletteHTTPException(401, "Not authenticated"))
    assert json.loads(response.body)["error"]["code"] == "HTTP_401"


def test_no_raw_http_exception_left_in_app():
    """Every error raised by the app carries an ErrorCode, so clients can localize it."""
    offenders = []
    for path in APP_DIR.rglob("*.py"):
        if path.name == "errors.py":
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "HTTPException":
                offenders.append(f"{path.relative_to(APP_DIR)}:{node.lineno}")
    assert offenders == []


@pytest.mark.parametrize(
    ("password", "code"),
    [
        ("Sh0rt!", ErrorCode.PASSWORD_TOO_SHORT),
        ("lowercase1!", ErrorCode.PASSWORD_NO_UPPERCASE),
        ("UPPERCASE1!", ErrorCode.PASSWORD_NO_LOWERCASE),
        ("NoDigits!!", ErrorCode.PASSWORD_NO_DIGIT),
        ("NoSpecial12", ErrorCode.PASSWORD_NO_SPECIAL),
    ],
)
def test_each_password_rule_maps_to_its_code(password, code):
    is_valid, message = validate_password_strength(password)
    assert not is_valid
    assert PASSWORD_ERROR_CODES[message] == code


def test_valid_password_passes():
    assert validate_password_strength("Secure123!") == (True, "")
