"""
Dummy Event Producer.

Stands in for Person A's domain services, which do not exist yet. Emits
CanonicalEvent instances directly — it is NOT wired through the producer
adapter, because there is no external payload shape to adapt from yet.
It's a convenience for manually triggering the automation chain during
this build session, not a permanent part of the architecture.

When A starts: this module is what gets DELETED. It is replaced by A's
real service + ProducerAdapter (see adapter.py), not modified in place.
"""
from __future__ import annotations

from app.automation.events import CanonicalEvent, EventType


def make_attendance_marked_event(
    student_id: str = "STU-001",
    subject_id: str = "SUB-101",
    attendance_percentage: int = 65,
    status: str = "ABSENT",
    aggregate_id: str = "ATT-001",
) -> CanonicalEvent:
    """Build a single dummy attendance.marked event with sane defaults."""
    return CanonicalEvent(
        event_type=EventType.ATTENDANCE_MARKED,
        aggregate_type="attendance",
        aggregate_id=aggregate_id,
        student_id=student_id,
        data={
            "subject_id": subject_id,
            "attendance_percentage": attendance_percentage,
            "status": status,
        },
    )


def make_fee_paid_event(
    student_id: str = "STU-001",
    amount: float = 5000.0,
    fee_type: str = "tuition",
    aggregate_id: str = "FEE-001",
) -> CanonicalEvent:
    """Second event type, per Step 16 optional work — kept minimal."""
    return CanonicalEvent(
        event_type=EventType.FEE_PAID,
        aggregate_type="fee",
        aggregate_id=aggregate_id,
        student_id=student_id,
        data={"amount": amount, "fee_type": fee_type},
    )


def make_hostel_allocated_event(
    student_id: str = "STU-001",
    hostel_code: str = "HOSTEL-A",
    room_number: str = "101",
    room_id: str = "ROOM-001",
    allocation_id: str = "ALLOC-001",
    aggregate_id: str = "ALLOC-001",
) -> CanonicalEvent:
    """Mirrors the real payload shape published by
    services/hostel.py's create_allocation() (see
    app/events/publisher.py's _adapt_hostel_allocated)."""
    return CanonicalEvent(
        event_type=EventType.HOSTEL_ALLOCATED,
        aggregate_type="hostel_allocation",
        aggregate_id=aggregate_id,
        student_id=student_id,
        data={
            "allocation_id": allocation_id,
            "student_id": student_id,
            "hostel_code": hostel_code,
            "room_id": room_id,
            "room_number": room_number,
            "allocated_at": "2026-01-01T00:00:00+00:00",
        },
    )


def make_exam_registered_event(
    student_id: str = "STU-001",
    exam_code: str = "EXAM-101",
    subject: str = "Data Structures",
    scheduled_at: str = "2026-05-01T09:00:00+00:00",
    registration_id: str = "REG-001",
    aggregate_id: str = "REG-001",
) -> CanonicalEvent:
    """Mirrors the real payload shape published by
    services/examination.py's register_student() (see
    app/events/publisher.py's _adapt_exam_registered)."""
    return CanonicalEvent(
        event_type=EventType.EXAM_REGISTERED,
        aggregate_type="exam_registration",
        aggregate_id=aggregate_id,
        student_id=student_id,
        data={
            "registration_id": registration_id,
            "student_id": student_id,
            "exam_code": exam_code,
            "subject": subject,
            "scheduled_at": scheduled_at,
        },
    )
