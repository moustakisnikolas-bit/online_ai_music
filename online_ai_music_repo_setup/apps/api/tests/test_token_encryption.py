import pytest

from app.services import token_encryption


class _EmptySettings:
    token_encryption_key = ""


class _InvalidKeySettings:
    token_encryption_key = "not-a-valid-fernet-key"


def test_encrypt_then_decrypt_round_trips(monkeypatch) -> None:
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode("utf-8")

    class _RealSettings:
        token_encryption_key = key

    monkeypatch.setattr(token_encryption, "get_settings", lambda: _RealSettings())

    cipher_text = token_encryption.encrypt_token("my-secret-refresh-token")

    assert cipher_text != "my-secret-refresh-token"
    assert token_encryption.decrypt_token(cipher_text) == "my-secret-refresh-token"


def test_falls_back_to_auto_generated_key_when_env_not_set(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(token_encryption, "get_settings", lambda: _EmptySettings())
    monkeypatch.setattr(token_encryption, "_LOCAL_KEY_FILE", tmp_path / ".local_secret_key")

    cipher_text = token_encryption.encrypt_token("my-secret")

    assert cipher_text != "my-secret"
    assert token_encryption.decrypt_token(cipher_text) == "my-secret"


def test_auto_generated_key_file_is_created_on_first_use(monkeypatch, tmp_path) -> None:
    key_file = tmp_path / ".local_secret_key"
    monkeypatch.setattr(token_encryption, "get_settings", lambda: _EmptySettings())
    monkeypatch.setattr(token_encryption, "_LOCAL_KEY_FILE", key_file)

    assert not key_file.exists()
    token_encryption.encrypt_token("secret")
    assert key_file.exists()


def test_auto_generated_key_file_is_reused_on_second_use(monkeypatch, tmp_path) -> None:
    key_file = tmp_path / ".local_secret_key"
    monkeypatch.setattr(token_encryption, "get_settings", lambda: _EmptySettings())
    monkeypatch.setattr(token_encryption, "_LOCAL_KEY_FILE", key_file)

    # A value encrypted before the file exists must still decrypt after --
    # proves the second call reuses the same key rather than generating a
    # fresh (and thus incompatible) one each time.
    cipher_text = token_encryption.encrypt_token("secret")
    key_after_first_use = key_file.read_text(encoding="utf-8")

    assert token_encryption.decrypt_token(cipher_text) == "secret"
    assert key_file.read_text(encoding="utf-8") == key_after_first_use


def test_explicit_env_key_takes_precedence_over_local_file(monkeypatch, tmp_path) -> None:
    from cryptography.fernet import Fernet

    env_key = Fernet.generate_key().decode("utf-8")
    key_file = tmp_path / ".local_secret_key"

    class _EnvSettings:
        token_encryption_key = env_key

    monkeypatch.setattr(token_encryption, "get_settings", lambda: _EnvSettings())
    monkeypatch.setattr(token_encryption, "_LOCAL_KEY_FILE", key_file)

    token_encryption.encrypt_token("secret")

    # The env var was used, so no local file should ever have been touched.
    assert not key_file.exists()


def test_encrypt_rejects_malformed_key(monkeypatch) -> None:
    monkeypatch.setattr(token_encryption, "get_settings", lambda: _InvalidKeySettings())

    with pytest.raises(ValueError, match="not a valid Fernet key"):
        token_encryption.encrypt_token("secret")


def test_decrypt_with_wrong_key_fails(monkeypatch) -> None:
    from cryptography.fernet import Fernet

    key_a = Fernet.generate_key().decode("utf-8")
    key_b = Fernet.generate_key().decode("utf-8")

    class _SettingsA:
        token_encryption_key = key_a

    class _SettingsB:
        token_encryption_key = key_b

    monkeypatch.setattr(token_encryption, "get_settings", lambda: _SettingsA())
    cipher_text = token_encryption.encrypt_token("secret")

    monkeypatch.setattr(token_encryption, "get_settings", lambda: _SettingsB())
    with pytest.raises(ValueError, match="could not be decrypted"):
        token_encryption.decrypt_token(cipher_text)
