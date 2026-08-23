from pydantic import BaseModel


class TriggerAttendanceMarkedRequest(BaseModel):
    student_id: str = "STU-001"
    subject_id: str = "SUB-101"
    attendance_percentage: int = 65
    status: str = "ABSENT"
    contact_email: str | None = None
    contact_phone: str | None = None


class TriggerFeePaidRequest(BaseModel):
    student_id: str = "STU-001"
    amount: float = 5000.0
    fee_type: str = "tuition"
    contact_email: str | None = None


class ActionResultRead(BaseModel):
    action: str
    status: str
    attempts: int
    error: str | None = None


class TriggerEventResponse(BaseModel):
    event_id: str
    event_type: str
    status: str  # workflow_triggered | no_rule_matched | skipped_duplicate
    workflow_id: str | None = None
    workflow_status: str | None = None
    actions: list[ActionResultRead] = []
