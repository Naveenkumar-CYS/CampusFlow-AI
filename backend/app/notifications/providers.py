"""
Notification providers.

    NotificationProvider (Protocol)
           |
      .send(to, subject, body) -> ProviderResult
           |
     -----------------
     |               |
  Email providers   SMS providers
  (Mock, SMTP)      (Mock, HTTP webhook)

The Notification Service (service.py) is the only thing that talks to
these directly. The Workflow Engine and Action Executor never see a
provider -- they see NotificationService.send_email / send_sms and a
ProviderResult.

Mock providers are the default everywhere. They never touch the network,
return a deterministic, realistic-shaped result, and are what the whole
automation chain runs against locally / in CI without any credentials.
"""
from __future__ import annotations

import json
import logging
import smtplib
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol

logger = logging.getLogger("campusflow.notifications.providers")


def _mask_contact(value: str) -> str:
    """Never log a full email/phone number -- just enough to eyeball in
    a log line that the right-looking contact was used."""
    if not value:
        return value
    if len(value) <= 4:
        return "*" * len(value)
    return f"{value[:2]}***{value[-2:]}"


@dataclass
class ProviderResult:
    """Structured result of a single provider send() call.

    `status` stays a plain "sent" / "failed" string (matches the shape
    Stage 3's actions.py already expects from provider_message_id /
    status), with `provider`, `channel`, and `error` added so a failure
    carries enough detail for the caller to decide what to do next,
    without the provider itself deciding retry/workflow behavior.
    """

    status: str  # "sent" | "failed"
    provider: str = "unknown"
    channel: str = ""  # "email" | "sms"
    provider_message_id: str | None = None
    error: str | None = None
    detail: str = ""


class NotificationProvider(Protocol):
    name: str

    def send(self, *, to: str, subject: str, body: str) -> ProviderResult: ...


# ---------------------------------------------------------------- mock ---


class MockEmailProvider:
    """Logs instead of sending. Same result shape a real provider would
    give, so swapping this out for SMTPEmailProvider is invisible to
    everything above NotificationService. Never sends anything real."""

    name = "mock_email"

    def send(self, *, to: str, subject: str, body: str) -> ProviderResult:
        message_id = f"mock-email-{uuid.uuid4()}"
        logger.info("MOCK EMAIL to=%s subject=%r id=%s", _mask_contact(to), subject, message_id)
        return ProviderResult(
            status="sent", provider=self.name, channel="email", provider_message_id=message_id
        )


class MockSMSProvider:
    """Same contract as MockEmailProvider, for the SMS channel."""

    name = "mock_sms"

    def send(self, *, to: str, subject: str, body: str) -> ProviderResult:
        message_id = f"mock-sms-{uuid.uuid4()}"
        logger.info("MOCK SMS to=%s id=%s", _mask_contact(to), message_id)
        return ProviderResult(
            status="sent", provider=self.name, channel="sms", provider_message_id=message_id
        )


# ---------------------------------------------------------------- smtp ---


class SMTPEmailProvider:
    """Real email via stdlib smtplib -- no extra dependency needed.

    Failures (connection refused, auth error, etc.) are caught here and
    turned into a failed ProviderResult rather than raising -- it's
    send_email() in actions.py (Stage 3's existing interface) that turns
    a failed result into an exception so the existing retry/dead-letter
    machinery picks it up. This provider never crashes the process.
    """

    name = "smtp"

    def __init__(
        self,
        host: str,
        port: int,
        username: str | None,
        password: str | None,
        from_email: str,
        use_tls: bool = True,
        timeout: int = 10,
    ):
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._from_email = from_email
        self._use_tls = use_tls
        self._timeout = timeout

    def send(self, *, to: str, subject: str, body: str) -> ProviderResult:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self._from_email
        message["To"] = to
        message.set_content(body)

        try:
            with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as smtp:
                if self._use_tls:
                    smtp.starttls()
                if self._username:
                    smtp.login(self._username, self._password or "")
                smtp.send_message(message)
        except (smtplib.SMTPException, OSError) as exc:
            logger.error("SMTP send failed to=%s: %s", _mask_contact(to), exc)
            return ProviderResult(status="failed", provider=self.name, channel="email", error=str(exc))

        message_id = f"smtp-{uuid.uuid4()}"
        logger.info("SMTP EMAIL SENT to=%s subject=%r id=%s", _mask_contact(to), subject, message_id)
        return ProviderResult(
            status="sent", provider=self.name, channel="email", provider_message_id=message_id
        )


# ---------------------------------------------------------------- sms ----


class HTTPSMSProvider:
    """Generic webhook-style SMS provider.

    Deliberately not tied to any specific paid SMS vendor's SDK -- it
    POSTs a small JSON payload {to, from, message} to a configurable
    URL (SMS_WEBHOOK_URL). Point this at whatever gateway the deployment
    actually uses (a self-hosted gateway, a serverless function fronting
    a real vendor, etc). Uses only the standard library.
    """

    name = "http_sms"

    def __init__(
        self,
        webhook_url: str,
        api_key: str | None = None,
        from_number: str | None = None,
        timeout: int = 10,
    ):
        self._webhook_url = webhook_url
        self._api_key = api_key
        self._from_number = from_number
        self._timeout = timeout

    def send(self, *, to: str, subject: str, body: str) -> ProviderResult:
        payload = json.dumps({"to": to, "from": self._from_number, "message": body}).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        request = urllib.request.Request(self._webhook_url, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                status_code = response.getcode()
                if status_code >= 400:
                    raise urllib.error.HTTPError(
                        self._webhook_url, status_code, "SMS webhook returned an error", None, None
                    )
        except (urllib.error.URLError, OSError) as exc:
            logger.error("SMS webhook send failed to=%s: %s", _mask_contact(to), exc)
            return ProviderResult(status="failed", provider=self.name, channel="sms", error=str(exc))

        message_id = f"http-sms-{uuid.uuid4()}"
        logger.info("SMS SENT to=%s id=%s", _mask_contact(to), message_id)
        return ProviderResult(
            status="sent", provider=self.name, channel="sms", provider_message_id=message_id
        )
