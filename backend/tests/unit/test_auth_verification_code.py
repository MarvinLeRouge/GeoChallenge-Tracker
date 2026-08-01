"""Tests for app.api.routes.auth.hash_verification_code."""

from app.api.routes.auth import hash_verification_code


class TestHashVerificationCode:
    def test_is_deterministic(self):
        assert hash_verification_code("abc123") == hash_verification_code("abc123")

    def test_different_codes_produce_different_hashes(self):
        assert hash_verification_code("abc123") != hash_verification_code("abc124")

    def test_returns_hex_sha256_digest(self):
        result = hash_verification_code("abc123")
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_does_not_return_the_plaintext_code(self):
        code = "my-secret-verification-code"
        assert hash_verification_code(code) != code
