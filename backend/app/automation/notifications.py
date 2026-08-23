"""
Notification Service.

    NotificationService
           |
     Provider interface
       /         \\
     Email        SMS

Mock providers only, for now (NOTIFICATION_MODE=mock). They log and
return a realistic provider-style result shape so swapping in a real
provider (SES, Twilio, whatever) later means writing a new Provider
implementation, not touching the workflow/action layer above it.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger("campusflow.automation.notifications")


@dataclass
class ProviderResult:
    provider_message_id: str
    status: str  # "sent" | "failed"
    detail: str = ""


class NotificationProvider(Protocol):
    def send(self, *, to: str, subject: str, body: str) -> ProviderResult: ...


class MockEmailProvider:
    """Logs instead of sending. Same result shape a real provider would give."""

    def send(self, *, to: str, subject: str, body: str) -> ProviderResult:
        message_id = f"mock-email-{uuid.uuid4()}"
        logger.info("MOCK EMAIL to=%s subject=%r id=%s", to, subject, message_id)
        return ProviderResult(provider_message_id=message_id, status="sent")


class MockSMSProvider:
    def send(self, *, to: str, subject: str, body: str) -> ProviderResult:
        message_id = f"mock-sms-{uuid.uuid4()}"
        logger.info("MOCK SMS to=%s body=%r id=%s", to, body, message_id)
        return ProviderResult(provider_message_id=message_id, status="sent")


class NotificationService:
    def __init__(
        self,
        email_provider: NotificationProvider | None = None,
        sms_provider: NotificationProvider | None = None,
    ):
        # Defaults are the mock providers -- this is what NOTIFICATION_MODE=mock
        # means in practice for local/hackathon dev. A settings-driven switch
        # to real providers is exactly the kind of thing that plugs in here
        # later without touching callers.
        self._email = email_provider or MockEmailProvider()
        self._sms = sms_provider or MockSMSProvider()

    def send_email(self, *, to: str, subject: str, body: str) -> ProviderResult:
        return self._email.send(to=to, subject=subject, body=body)

    def send_sms(self, *, to: str, body: str) -> ProviderResult:
        return self._sms.send(to=to, subject="", body=body)
