import hashlib
import secrets

from backend.src.services.user_service import UserService


def test_hash_password_uses_pbkdf2_scheme() -> None:
    service = UserService()
    hashed, salt = service._hash_password("super-secret")

    assert salt
    assert hashed.startswith("pbkdf2_sha256$")
    assert service._verify_password("super-secret", hashed)
    assert not service._verify_password("wrong", hashed)


def test_verify_password_supports_legacy_sha256_format() -> None:
    service = UserService()

    salt = secrets.token_hex(16)
    legacy_hash = hashlib.sha256(f"{salt}:password123".encode("utf-8")).hexdigest()
    stored = f"{salt}:{legacy_hash}"

    is_valid, should_rehash = service._verify_password_with_rehash("password123", stored)
    assert is_valid
    assert should_rehash
