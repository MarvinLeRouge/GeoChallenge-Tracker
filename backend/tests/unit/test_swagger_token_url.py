"""The OpenAPI token URL follows UVICORN_ROOT_PATH, so Swagger's Authorize hits the API."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _token_url(root_path: str | None) -> str:
    env = {k: v for k, v in os.environ.items() if k != "UVICORN_ROOT_PATH"}
    if root_path is not None:
        env["UVICORN_ROOT_PATH"] = root_path
    # fresh interpreter: the scheme is built at import time
    out = (
        subprocess.run(
            [
                sys.executable,
                "-c",
                "import json; from app.main import app; print(json.dumps(app.openapi()))",
            ],
            cwd=BACKEND_DIR,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        .stdout.strip()
        .splitlines()[-1]
    )
    schemes = json.loads(out)["components"]["securitySchemes"]
    return schemes["OAuth2PasswordBearer"]["flows"]["password"]["tokenUrl"]


@pytest.mark.parametrize(
    ("root_path", "expected"),
    [("/api", "/api/auth/login"), ("/api/", "/api/auth/login"), (None, "/auth/login")],
)
def test_token_url_follows_the_root_path(root_path, expected):
    assert _token_url(root_path) == expected
