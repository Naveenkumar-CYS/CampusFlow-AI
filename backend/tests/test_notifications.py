"""
Stage 4 -- Notification Service tests.

Deliberately network-free: SMTP/HTTP-SMS providers are tested for
config parsing and failure handling using monkeypatched/unreachable
targets, never a real server. Mirrors the DB-free style of
test_automation.py.
"""
from __future__ import annotations

import pytest

from app.automation.actions import (
    ACTION_REGISTRY,
    ActionExecutor,
    create_notification,
    send_email,
    send_sms,
)
from app.automation.producer import (
    make_attendance_marked_event,
    make_exam_registered_event,
    make_fee_paid_event,
    make_hostel_allocated_event,
)
from app.notifications.providers import (
    HTTPSMSProvider,
    MockEmailProvider,
    MockSMSProvider,
    ProviderResult,
    SMTPEmailProvider,
)
from app.notifications.service import (
    NotificationConfigError,
    NotificationService,
    build_email_provider,
    build_notification_service,
    build_sms_provider,
)
from app.notifications.templates import (
    build_attendance_warning_message,
    build_exam_registration_confirmation_message,
    build_fee_confirmation_message,
    build_hostel_allocation_confirmation_message,
)


class FakeSettings:
    """Minimal settings stand-in -- avoids needing a real .env / Settings()
    for provider-selection tests."""

    def __init__(self, **overrides):
        self.notification_provider_mode = "mock"
        self.smtp_host = None
        self.smtp_port = 587
        self.smtp_username = None
        self.smtp_password = None
        self.smtp_from_email = None
        self.smtp_use_tls = True
        self.sms_webhook_url = None
        self.sms_api_key = None
        self.sms_from_number = None
        for key, value in overrides.items():
            setattr(self, key, value)


# ---------------------------------------------------------------- mock ---


def test_mock_email_provider_returns_deterministic_success():
    provider = MockEmailProvider()
    result = provider.send(to="student@example.edu", subject="Hi", body="Body text")

    assert isinstance(result, ProviderResult)
    assert result.status == "sent"
    assert result.channel == "email"
    assert result.provider == "mock_email"
    assert result.provider_message_id.startswith("mock-email-")
    assert result.error is None


def test_mock_email_provider_never_sends_real_mail(monkeypatch):
    # If MockEmailProvider ever tried to open a real SMTP connection this
    # would blow up (no server listening) -- proves it doesn't.
    import smtplib

    def _boom(*args, **kwargs):
        raise AssertionError("MockEmailProvider must never touch smtplib")

    monkeypatch.setattr(smtplib, "SMTP", _boom)
    provider = MockEmailProvider()
    result = provider.send(to="student@example.edu", subject="Hi", body="Body")
    assert result.status == "sent"


def test_mock_sms_provider_returns_deterministic_success():
    provider = MockSMSProvider()
    result = provider.send(to="+911234567890", subject="", body="Your OTP is 1234")

    assert result.status == "sent"
    assert result.channel == "sms"
    assert result.provider == "mock_sms"
    assert result.provider_message_id.startswith("mock-sms-")


def test_notification_service_uses_mocks_by_default():
    service = NotificationService(settings=FakeSettings())
    email_result = service.send_email(to="a@b.com", subject="s", body="b")
    sms_result = service.send_sms(to="+911111111111", body="b")

    assert email_result.status == "sent" and email_result.provider == "mock_email"
    assert sms_result.status == "sent" and sms_result.provider == "mock_sms"


# ---------------------------------------------------------- provider selection ---


def test_build_email_provider_mock_mode():
    provider = build_email_provider(FakeSettings(notification_provider_mode="mock"))
    assert isinstance(provider, MockEmailProvider)


def test_build_sms_provider_mock_mode():
    provider = build_sms_provider(FakeSettings(notification_provider_mode="mock"))
    assert isinstance(provider, MockSMSProvider)


def test_build_email_provider_live_mode_with_valid_config():
    settings = FakeSettings(
        notification_provider_mode="live",
        smtp_host="smtp.example.com",
        smtp_from_email="noreply@example.com",
    )
    provider = build_email_provider(settings)
    assert isinstance(provider, SMTPEmailProvider)


def test_build_sms_provider_live_mode_with_valid_config():
    settings = FakeSettings(
        notification_provider_mode="live", sms_webhook_url="https://sms.example.com/send"
    )
    provider = build_sms_provider(settings)
    assert isinstance(provider, HTTPSMSProvider)


def test_build_email_provider_live_mode_missing_config_raises():
    settings = FakeSettings(notification_provider_mode="live")  # no smtp_host
    with pytest.raises(NotificationConfigError):
        build_email_provider(settings)


def test_build_sms_provider_live_mode_missing_config_raises():
    settings = FakeSettings(notification_provider_mode="live")  # no sms_webhook_url
    with pytest.raises(NotificationConfigError):
        build_sms_provider(settings)


def test_invalid_provider_mode_raises():
    settings = FakeSettings(notification_provider_mode="carrier-pigeon")
    with pytest.raises(NotificationConfigError):
        build_email_provider(settings)
    with pytest.raises(NotificationConfigError):
        build_sms_provider(settings)


def test_build_notification_service_from_explicit_settings():
    settings = FakeSettings(notification_provider_mode="mock")
    service = build_notification_service(settings)
    assert isinstance(service, NotificationService)
    result = service.send_email(to="a@b.com", subject="s", body="b")
    assert result.status == "sent"


# --------------------------------------------------------------- smtp ----


def test_smtp_provider_config_parsing():
    provider = SMTPEmailProvider(
        host="smtp.example.com",
        port=2525,
        username="user",
        password="pw",
        from_email="noreply@example.com",
        use_tls=True,
    )
    assert provider._host == "smtp.example.com"
    assert provider._port == 2525
    assert provider._use_tls is True


def test_smtp_provider_failure_is_caught_and_returns_structured_result():
    # Nothing listens on this port -- smtplib.SMTP() will raise
    # ConnectionRefusedError/OSError, which the provider must catch.
    provider = SMTPEmailProvider(
        host="127.0.0.1",
        port=1,  # reserved, guaranteed nothing is listening
        username=None,
        password=None,
        from_email="noreply@example.com",
        use_tls=False,
        timeout=1,
    )
    result = provider.send(to="student@example.edu", subject="Hi", body="Body")

    assert result.status == "failed"
    assert result.provider == "smtp"
    assert result.channel == "email"
    assert result.error is not None
    assert result.provider_message_id is None


def test_smtp_provider_tls_flag_does_not_raise_when_disabled():
    provider = SMTPEmailProvider(
        host="127.0.0.1", port=1, username=None, password=None,
        from_email="a@b.com", use_tls=False, timeout=1,
    )
    result = provider.send(to="x@y.com", subject="s", body="b")
    # Still fails (nothing listening), but must not raise out of send().
    assert result.status == "failed"


# ------------------------------------------------------------- http sms --


def test_http_sms_provider_failure_is_caught_and_returns_structured_result():
    provider = HTTPSMSProvider(webhook_url="http://127.0.0.1:1/send", timeout=1)
    result = provider.send(to="+911234567890", subject="", body="hi")

    assert result.status == "failed"
    assert result.provider == "http_sms"
    assert result.channel == "sms"
    assert result.error is not None


# ----------------------------------------------------------- templates ---


def test_low_attendance_template_uses_event_data():
    event = make_attendance_marked_event(
        student_id="STU-777", subject_id="SUB-42", attendance_percentage=48
    )
    subject, body = build_attendance_warning_message(event)

    assert subject == "Low Attendance Warning"
    assert "48%" in body
    assert "SUB-42" in body


def test_fee_confirmation_template_uses_event_data():
    event = make_fee_paid_event(student_id="STU-888", amount=2500.5, fee_type="hostel")
    subject, body = build_fee_confirmation_message(event)

    assert subject == "Fee Payment Confirmation"
    assert "2500.5" in body
    assert "hostel" in body


def test_hostel_allocation_template_uses_event_data():
    event = make_hostel_allocated_event(
        student_id="STU-321", hostel_code="HOSTEL-B", room_number="204"
    )
    subject, body = build_hostel_allocation_confirmation_message(event)

    assert subject == "Hostel Allocation Confirmation"
    assert "HOSTEL-B" in body
    assert "204" in body


def test_exam_registration_template_uses_event_data():
    event = make_exam_registered_event(
        student_id="STU-654", exam_code="EXAM-202", subject="Operating Systems"
    )
    subject, body = build_exam_registration_confirmation_message(event)

    assert subject == "Exam Registration Confirmation"
    assert "EXAM-202" in body
    assert "Operating Systems" in body


def test_templates_do_not_hardcode_one_students_details():
    event_a = make_attendance_marked_event(student_id="STU-A", attendance_percentage=10)
    event_b = make_attendance_marked_event(student_id="STU-B", attendance_percentage=90)

    _, body_a = build_attendance_warning_message(event_a)
    _, body_b = build_attendance_warning_message(event_b)

    assert body_a != body_b
    assert "10%" in body_a
    assert "90%" in body_b


# ---------------------------------------------------------- contact resolution ---


def test_contact_resolution_prefers_event_provided_contact():
    from app.automation.actions import _resolve_student_contact

    event = make_attendance_marked_event()
    event.data["contact_email"] = "explicit@example.edu"
    event.data["contact_phone"] = "+910000000001"

    email, phone = _resolve_student_contact(event, {})

    assert email == "explicit@example.edu"
    assert phone == "+910000000001"


def test_contact_resolution_falls_back_to_safe_placeholder_without_db():
    from app.automation.actions import _resolve_student_contact

    event = make_attendance_marked_event(student_id="STU-999")
    email, phone = _resolve_student_contact(event, {})

    assert email == "STU-999@example.edu"
    assert phone == "+91-0000000000"


# -------------------------------------------------------- failure handling ---


class _AlwaysFailingProvider:
    name = "always_fails"

    def send(self, *, to, subject, body):
        return ProviderResult(status="failed", provider=self.name, channel="email", error="simulated outage")


def test_send_email_action_raises_on_provider_failure():
    service = NotificationService(email_provider=_AlwaysFailingProvider(), sms_provider=MockSMSProvider())
    event = make_attendance_marked_event()
    context = {"notification_service": service, "notification": {"subject": "s", "body": "b"}}

    with pytest.raises(RuntimeError, match="email provider failed"):
        send_email(event, context)


def test_action_executor_turns_provider_failure_into_structured_action_failure():
    """provider failure -> structured failure -> Action Executor receives it,
    via the EXISTING retry/failure mechanism (no new retry system added)."""
    service = NotificationService(email_provider=_AlwaysFailingProvider(), sms_provider=MockSMSProvider())
    event = make_attendance_marked_event()
    context = {"notification_service": service}

    registry = dict(ACTION_REGISTRY)
    executor = ActionExecutor(max_attempts=2, registry=registry)

    create_result = executor.execute("create_notification", event, context)
    assert create_result.status == "success"

    send_result = executor.execute("send_email", event, context)
    assert send_result.status == "failed"
    assert send_result.attempts == 2  # existing retry mechanism kicked in
    assert "email provider failed" in send_result.error


def test_send_sms_action_raises_on_provider_failure():
    class AlwaysFailingSMS:
        name = "always_fails_sms"

        def send(self, *, to, subject, body):
            return ProviderResult(status="failed", provider=self.name, channel="sms", error="simulated outage")

    service = NotificationService(email_provider=MockEmailProvider(), sms_provider=AlwaysFailingSMS())
    event = make_attendance_marked_event()
    context = {"notification_service": service, "notification": {"subject": "s", "body": "b"}}

    with pytest.raises(RuntimeError, match="sms provider failed"):
        send_sms(event, context)


def test_send_email_action_succeeds_with_mock_provider_end_to_end():
    service = NotificationService(email_provider=MockEmailProvider(), sms_provider=MockSMSProvider())
    event = make_attendance_marked_event()
    context: dict = {"notification_service": service}

    create_notification(event, context)
    result = send_email(event, context)

    assert result["status"] == "sent"
    assert result["provider"] == "mock_email"
    assert result["provider_message_id"].startswith("mock-email-")
