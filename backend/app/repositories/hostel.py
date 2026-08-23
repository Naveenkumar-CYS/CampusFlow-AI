import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.hostel import AllocationStatus, Hostel, HostelAllocation, Room

# --------------------------------------------------------------------- Hostel


def create_hostel(db: Session, *, hostel_code: str, name: str) -> Hostel:
    hostel = Hostel(hostel_code=hostel_code, name=name)
    db.add(hostel)
    db.commit()
    db.refresh(hostel)
    return hostel


def get_hostel_by_id(db: Session, hostel_pk: uuid.UUID) -> Hostel | None:
    return db.get(Hostel, hostel_pk)


def get_hostel_by_code(db: Session, hostel_code: str) -> Hostel | None:
    return db.scalar(select(Hostel).where(Hostel.hostel_code == hostel_code))


def list_hostels(db: Session) -> list[Hostel]:
    return list(db.scalars(select(Hostel).order_by(Hostel.created_at)))


def update_hostel(db: Session, hostel: Hostel, changes: dict) -> Hostel:
    for field, value in changes.items():
        setattr(hostel, field, value)
    db.commit()
    db.refresh(hostel)
    return hostel


def delete_hostel(db: Session, hostel: Hostel) -> None:
    db.delete(hostel)
    db.commit()


# ------------------------------------------------------------------------ Room


def create_room(db: Session, *, hostel_pk: uuid.UUID, room_number: str, capacity: int) -> Room:
    room = Room(hostel_id=hostel_pk, room_number=room_number, capacity=capacity)
    db.add(room)
    db.commit()
    db.refresh(room)
    return room


def get_room_by_id(db: Session, room_pk: uuid.UUID) -> Room | None:
    return db.get(Room, room_pk)


def get_room_by_hostel_and_number(
    db: Session, hostel_pk: uuid.UUID, room_number: str
) -> Room | None:
    return db.scalar(
        select(Room).where(Room.hostel_id == hostel_pk, Room.room_number == room_number)
    )


def list_rooms(db: Session, *, hostel_pk: uuid.UUID | None = None) -> list[Room]:
    stmt = select(Room).order_by(Room.created_at)
    if hostel_pk is not None:
        stmt = stmt.where(Room.hostel_id == hostel_pk)
    return list(db.scalars(stmt))


def update_room(db: Session, room: Room, changes: dict) -> Room:
    for field, value in changes.items():
        setattr(room, field, value)
    db.commit()
    db.refresh(room)
    return room


def delete_room(db: Session, room: Room) -> None:
    db.delete(room)
    db.commit()


def increment_occupancy(db: Session, room: Room) -> Room:
    room.current_occupancy += 1
    db.commit()
    db.refresh(room)
    return room


def decrement_occupancy(db: Session, room: Room) -> Room:
    room.current_occupancy = max(0, room.current_occupancy - 1)
    db.commit()
    db.refresh(room)
    return room


# ------------------------------------------------------------------ Allocation


def create_allocation(
    db: Session, *, student_pk: uuid.UUID, room_pk: uuid.UUID
) -> HostelAllocation:
    allocation = HostelAllocation(student_id=student_pk, room_id=room_pk)
    db.add(allocation)
    db.commit()
    db.refresh(allocation)
    return allocation


def get_allocation_by_id(db: Session, allocation_pk: uuid.UUID) -> HostelAllocation | None:
    return db.get(HostelAllocation, allocation_pk)


def get_active_allocation_for_student(
    db: Session, student_pk: uuid.UUID
) -> HostelAllocation | None:
    return db.scalar(
        select(HostelAllocation).where(
            HostelAllocation.student_id == student_pk,
            HostelAllocation.status == AllocationStatus.ACTIVE,
        )
    )


def list_allocations(
    db: Session, *, student_pk: uuid.UUID | None = None, room_pk: uuid.UUID | None = None
) -> list[HostelAllocation]:
    stmt = select(HostelAllocation).order_by(HostelAllocation.created_at)
    if student_pk is not None:
        stmt = stmt.where(HostelAllocation.student_id == student_pk)
    if room_pk is not None:
        stmt = stmt.where(HostelAllocation.room_id == room_pk)
    return list(db.scalars(stmt))


def set_allocation_status(
    db: Session, allocation: HostelAllocation, status: AllocationStatus
) -> HostelAllocation:
    allocation.status = status
    allocation.vacated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(allocation)
    return allocation


def delete_allocation(db: Session, allocation: HostelAllocation) -> None:
    db.delete(allocation)
    db.commit()
