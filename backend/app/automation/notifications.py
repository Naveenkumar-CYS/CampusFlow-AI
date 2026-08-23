"""
Notification Service -- backward-compatible import shim.

The real implementation lives in app/notifications/ (providers.py,
service.py, templates.py) as of Stage 4. This module is kept so the
existing Stage 3 import path

    from app.automation.notifications import NotificationService

(used by app/automation/actions.py and app/automation/workflows.py)
keeps working unchanged -- Stage 3 code was not touched to point at the
new location. There is exactly one NotificationService implementation;
nothing here is a second copy.
"""
from __future__ import annotations

from app.notifications.providers import (  # noqa: F401
    HTTPSMSProvider,
    MockEmailProvider,
    MockSMSProvider,
    NotificationProvider,
    ProviderResult,
    SMTPEmailProvider,
)
from app.notifications.service import (  # noqa: F401
    NotificationConfigError,
    NotificationService,
    build_email_provider,
    build_notification_service,
    build_sms_provider,
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
]
