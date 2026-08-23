import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.fee import FeeStatus


class FeeCreate(BaseModel):
    fee_id: str
    student_id: str  # human-readable Student.student_id, resolved to the FK server-side
    fee_type: str
    amount: Decimal = Field(gt=0)
    due_date: date


class FeeUpdate(BaseModel):
    """Partial update. Does NOT allow changing status/payment fields directly
    -- those only ever change via the /fees/{fee_id}/pay operation, so a
    valid state transition is always enforced (see Phase 4 critical rule)."""
    fee_type: str | None = None
    amount: Decimal | None = Field(default=None, gt=0)
    due_date: date | None = None


class FeePayRequest(BaseModel):
    payment_reference: str


class FeeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    fee_id: str
    student_id: uuid.UUID
    fee_type: str
    amount: Decimal
    due_date: date
    status: FeeStatus
    payment_reference: str | None
    paid_at: datetime | None
    created_at: datetime
    updated_at: datetime
