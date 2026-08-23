"""
Notification Service (Stage 4).

    Action Executor
           |
    NotificationService
           |
     Provider interface
       /         \\
     Email        SMS

Public entry points re-exported here:

    NotificationService        -- what callers (actions.py) use
    build_notification_service -- settings-driven factory
    ProviderResult              -- structured send() result
    NotificationConfigError     -- raised for invalid provider config

Everything under this package is new/owned by Stage 4. Stage 3
(actions.py / workflows.py) only ever imports `NotificationService` --
see app/automation/notifications.py, which re-exports from here so that
existing import path keeps working unchanged.
"""
from __future__ import annotations

from app.notifications.providers import (
    HTTPSMSProvider,
    MockEmailProvider,
    MockSMSProvider,
    NotificationProvider,
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
    TEMPLATE_REGISTRY,
    build_attendance_warning_message,
    build_fee_confirmation_message,
)

__all__ = [
    "NotificationProvider",
    "ProviderResult",
    "MockEmailProvider",
    "MockSMSProvider",
    "SMTPEmailProvider",
    "HTTPSMSProvider",
    "NotificationService",
    "NotificationConfigError",
    "build_notification_service",
    "build_email_provider",
    "build_sms_provider",
    "TEMPLATE_REGISTRY",
    "build_attendance_warning_message",
    "build_fee_confirmation_message",
]
