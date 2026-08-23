from cryptography.fernet import Fernet, InvalidToken

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