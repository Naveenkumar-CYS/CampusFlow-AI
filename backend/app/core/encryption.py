from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import String
from sqlalchemy.types import TypeDecorator

from app.core.config import get_settings


def _get_fernet() -> Fernet:
    settings = get_settings()

    if not settings.encryption_key:
        raise RuntimeError(
            "ENCRYPTION_KEY is not configured. "
            "Set a valid Fernet key in the environment."
        )

    return Fernet(settings.encryption_key.encode())


def encrypt_value(value: str | None) -> str | None:
    """Encrypt a sensitive string before storing it in the database."""
    if value is None:
        return None

    return _get_fernet().encrypt(value.encode()).decode()


def decrypt_value(value: str | None) -> str | None:
    """Decrypt a sensitive string read from the database."""
    if value is None:
        return None

    try:
        return _get_fernet().decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Unable to decrypt stored value.") from exc


class EncryptedString(TypeDecorator):
    """SQLAlchemy column type that transparently encrypts a string value
    before it is written to the database and decrypts it on the way back
    out, using encrypt_value()/decrypt_value() above.

    Wired into ONLY Student.phone for this session (see Person E Step 2
    notes in backend/README.md) -- a genuinely sensitive, non-indexed,
    non-unique, non-filtered field. Do not reach for this type for
    primary/foreign keys or anything the app searches/filters on: Fernet
    ciphertext is non-deterministic (a different value each time the same
    plaintext is encrypted), so equality/LIKE queries against an
    encrypted column silently stop working.

    impl=String so the underlying DB column is a plain VARCHAR containing
    the (longer) ciphertext -- callers must size the column generously
    rather than to the plaintext's natural length.
    """

    impl = String
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect) -> str | None:
        return encrypt_value(value)

    def process_result_value(self, value: str | None, dialect) -> str | None:
        return decrypt_value(value)