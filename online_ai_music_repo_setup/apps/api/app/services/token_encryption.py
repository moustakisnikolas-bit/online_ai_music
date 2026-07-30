import logging
import os
from functools import lru_cache
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# apps/api/.local_secret_key -- anchored to this file's own location, not
# the process's current working directory. Two different processes in this
# project (the API server and the worker) have been bitten before by a
# relative path resolving differently depending on which directory each
# was launched from; anchoring to __file__ avoids that class of bug here.
_LOCAL_KEY_FILE = Path(__file__).resolve().parents[2] / ".local_secret_key"


def _load_or_create_local_key() -> str:
    # Auto-generated fallback so nobody has to hand-create
    # TOKEN_ENCRYPTION_KEY before the app can encrypt anything -- used only
    # when the env var isn't set. Created on first use, reused after that.
    #
    # Deployment note: this file lives on whatever filesystem the process
    # sees. That's fine for a laptop, but if this ever runs inside a
    # container/VPS setup where the app's own directory isn't on a
    # persistent volume, recreating the container regenerates this key --
    # and every secret encrypted with the old one becomes unreadable, even
    # though the encrypted rows are still sitting in the database. The env
    # var path above exists specifically so a real deployment can pin a
    # stable key instead of relying on this fallback; the warning below is
    # a runtime nudge toward that, not just something buried in docs.
    try:
        return _LOCAL_KEY_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        pass

    new_key = Fernet.generate_key().decode("utf-8")

    try:
        # O_EXCL: fails instead of overwriting if the file appeared between
        # our read attempt above and this create -- a second process losing
        # that race reads back whatever the winner actually wrote, rather
        # than the two processes silently disagreeing on the key.
        fd = os.open(_LOCAL_KEY_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            os.write(fd, new_key.encode("utf-8"))
        finally:
            os.close(fd)
        logger.warning(
            "Generated a new encryption key at %s (no TOKEN_ENCRYPTION_KEY "
            "env var was set). Fine for local use. Before deploying anywhere "
            "the app's own files might not persist (a VPS, a container "
            "rebuild), set TOKEN_ENCRYPTION_KEY explicitly instead, or "
            "saved API keys will become unreadable if this file is lost.",
            _LOCAL_KEY_FILE,
        )
        return new_key
    except FileExistsError:
        return _LOCAL_KEY_FILE.read_text(encoding="utf-8").strip()


@lru_cache(maxsize=4)
def _build_fernet(key: str) -> Fernet:
    # Keyed by the key string itself (not a no-arg cache) so a changed
    # TOKEN_ENCRYPTION_KEY -- including across tests that swap settings --
    # builds a fresh cipher instead of reusing a stale one, while a stable
    # key (the normal case) skips re-deriving the cipher on every call.
    try:
        return Fernet(key.encode("utf-8"))
    except ValueError as exc:
        raise ValueError(
            "TOKEN_ENCRYPTION_KEY is not a valid Fernet key (must be a "
            "32-byte URL-safe base64-encoded string)."
        ) from exc


def _fernet() -> Fernet:
    settings = get_settings()

    # An explicit env var always wins (e.g. a real server deployment where
    # an operator wants to manage it deliberately); otherwise fall back to
    # the auto-generated local file so there's no manual setup step at all
    # for local/desktop use.
    key = settings.token_encryption_key or _load_or_create_local_key()

    return _build_fernet(key)


def encrypt_token(plain_text: str) -> str:
    return _fernet().encrypt(plain_text.encode("utf-8")).decode("utf-8")


def decrypt_token(cipher_text: str) -> str:
    try:
        return _fernet().decrypt(cipher_text.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError(
            "Stored token could not be decrypted (wrong TOKEN_ENCRYPTION_KEY "
            "or corrupted data)."
        ) from exc
