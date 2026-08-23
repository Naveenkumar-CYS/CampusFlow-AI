"""
Notification Service + provider selection.

    NotificationService
           |
    email_provider / sms_provider
           |
     built by build_notification_service(), which reads
     Settings.notification_provider_mode (NOTIFICATION_PROVIDER_MODE)

NOTIFICATION_PROVIDER_MODE=mock (the default -- see Settings) selects
MockEmailProvider / MockSMSProvider. This is what lets the whole
automation chain run with zero credentials. NOTIFICATION_PROVIDER_MODE=live
selects the real SMTP / HTTP-webhook SMS providers, and requires their
respective config to actually be present -- see build_email_provider /
build_sms_provider below. There's exactly one place that branches on
provider mode; nothing else in the codebase checks NOTIFICATION_PROVIDER_MODE
or reads SMTP_*/SMS_* directly.
"""
from __future__ import annotations

import logging

from app.notifications.providers import (
    HTTPSMSProvider,
    MockEmailProvider,
    MockSMSProvider,
    NotificationProvider,
    ProviderResult,
    SMTPEmailProvider,
)

logger = logging.getLogger("campusflow.notifications.service")


class NotificationConfigError(ValueError):
    """Raised when NOTIFICATION_PROVIDER_MODE (or a provider's required
    config) is invalid -- e.g. mode=live without SMTP_HOST set."""


def build_email_provider(settings) -> NotificationProvider:
    mode = (settings.notification_provider_mode or "mock").lower()

    if mode == "mock":
        return MockEmailProvider()

    if mode == "live":
        if not settings.smtp_host or not settings.smtp_from_email:
            raise NotificationConfigError(
                "NOTIFICATION_PROVIDER_MODE=live requires SMTP_HOST and "
                "SMTP_FROM_EMAIL to be set for the email provider"
            )
        return SMTPEmailProvider(
            host=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password,
            from_email=settings.smtp_from_email,
            use_tls=settings.smtp_use_tls,
        )

    raise NotificationConfigError(f"unknown NOTIFICATION_PROVIDER_MODE: {settings.notification_provider_mode!r}")


def build_sms_provider(settings) -> NotificationProvider:
    mode = (settings.notification_provider_mode or "mock").lower()

    if mode == "mock":
        return MockSMSProvider()

    if mode == "live":
        if not settings.sms_webhook_url:
            raise NotificationConfigError(
                "NOTIFICATION_PROVIDER_MODE=live requires SMS_WEBHOOK_URL to "
                "be set for the SMS provider"
            )
        return HTTPSMSProvider(
            webhook_url=settings.sms_webhook_url,
            api_key=settings.sms_api_key,
            from_number=settings.sms_from_number,
        )

    raise NotificationConfigError(f"unknown NOTIFICATION_PROVIDER_MODE: {settings.notification_provider_mode!r}")


class NotificationService:
    """The only notification boundary the Workflow/Action layer talks to.

    Stage 3's actions.py calls .send_email(...) / .send_sms(...) and gets
    back a ProviderResult -- it never knows or cares whether the
    underlying provider is a mock, SMTP, or an HTTP SMS webhook.
    """

    def __init__(
        self,
        email_provider: NotificationProvider | None = None,
        sms_provider: NotificationProvider | None = None,
        settings=None,
    ):
        if email_provider is None or sms_provider is None:
            # Only touch settings if we actually need a default -- callers
            # that pass explicit providers (e.g. tests) never require
            # Settings() to be constructible.
            if settings is None:
                from app.core.config import get_settings

                settings = get_settings()
            email_provider = email_provider or build_email_provider(settings)
            sms_provider = sms_provider or build_sms_provider(settings)

        self._email = email_provider
        self._sms = sms_provider

    def send_email(self, *, to: str, subject: str, body: str) -> ProviderResult:
        return self._email.send(to=to, subject=subject, body=body)

    def send_sms(self, *, to: str, body: str) -> ProviderResult:
        return self._sms.send(to=to, subject="", body=body)


def build_notification_service(settings=None) -> NotificationService:
    """Explicit factory, for callers that want to construct a service
    from a specific Settings instance (e.g. tests exercising provider
    selection) rather than relying on NotificationService()'s implicit
    get_settings() default."""
    if settings is None:
        from app.core.config import get_settings

        settings = get_settings()
    return NotificationService(
        email_provider=build_email_provider(settings),
        sms_provider=build_sms_provider(settings),
        settings=settings,
    )
