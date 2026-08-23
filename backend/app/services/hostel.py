from sqlalchemy.orm import Session

from app.events.publisher import publish
from app.models.hostel import AllocationStatus, Hostel, HostelAllocation, Room
from app.repositories import hostel as hostel_repo
from app.repositories import student as student_repo
from app.schemas.hostel import (
    AllocationCreate,
    AllocationUpdate,
    HostelCreate,
    HostelUpdate,
    RoomCreate,
    RoomUpdate,
)


class DuplicateHostelError(Exception):
    pass


class DuplicateRoomError(Exception):
    pass


class HostelNotFoundError(Exception):
    pass


class StudentNotFoundError(Exception):
    pass


class RoomNotFoundError(Exception):
    pass


class RoomFullError(Exception):
    pass


class DuplicateActiveAllocationError(Exception):
    """Raised when the student already has an ACTIVE allocation."""
    pass


class InvalidAllocationStateTransitionError(Exception):
    """Raised when trying to move an allocation to/from a status that
    isn't a valid transition (e.g. re-vacating an already-VACATED row)."""
    pass


# --------------------------------------------------------------------- Hostel


def create_hostel(db: Session, data: HostelCreate) -> Hostel:
    if hostel_repo.get_hostel_by_code(db, data.hostel_code) is not None:
        raise DuplicateHostelError(f"hostel_code '{data.hostel_code}' already exists")
    return hostel_repo.create_hostel(db, hostel_code=data.hostel_code, name=data.name)


def get_hostel(db: Session, hostel_code: str) -> Hostel | None:
    return hostel_repo.get_hostel_by_code(db, hostel_code)


def list_hostels(db: Session) -> list[Hostel]:
    return hostel_repo.list_hostels(db)


def update_hostel(db: Session, hostel_code: str, data: HostelUpdate) -> Hostel | None:
    hostel = hostel_repo.get_hostel_by_code(db, hostel_code)
    if hostel is None:
        return None
    changes = data.model_dump(exclude_unset=True)
    if not changes:
        return hostel
    return hostel_repo.update_hostel(db, hostel, changes)


def delete_hostel(db: Session, hostel_code: str) -> bool:
    hostel = hostel_repo.get_hostel_by_code(db, hostel_code)
    if hostel is None:
        return False
    hostel_repo.delete_hostel(db, hostel)  # FK RESTRICT raises IntegrityError if Rooms exist
    return True


# ------------------------------------------------------------------------ Room


def create_room(db: Session, data: RoomCreate) -> Room:
    hostel = hostel_repo.get_hostel_by_code(db, data.hostel_code)
    if hostel is None:
        raise HostelNotFoundError(f"hostel '{data.hostel_code}' not found")

    if hostel_repo.get_room_by_hostel_and_number(db, hostel.id, data.room_number) is not None:
        raise DuplicateRoomError(
            f"room '{data.room_number}' already exists in hostel '{data.hostel_code}'"
        )

    return hostel_repo.create_room(
        db, hostel_pk=hostel.id, room_number=data.room_number, capacity=data.capacity
    )


def get_room(db: Session, room_id) -> Room | None:
    return hostel_repo.get_room_by_id(db, room_id)


def list_rooms(db: Session, *, hostel_code: str | None = None) -> list[Room]:
    hostel_pk = None
    if hostel_code is not None:
        hostel = hostel_repo.get_hostel_by_code(db, hostel_code)
        if hostel is None:
            raise HostelNotFoundError(f"hostel '{hostel_code}' not found")
        hostel_pk = hostel.id
    return hostel_repo.list_rooms(db, hostel_pk=hostel_pk)


def update_room(db: Session, room_id, data: RoomUpdate) -> Room | None:
    room = hostel_repo.get_room_by_id(db, room_id)
    if room is None:
        return None
    changes = data.model_dump(exclude_unset=True)
    if not changes:
        return room
    # Shrinking capacity below current occupancy would silently violate
    # the "current_occupancy <= capacity" invariant the DB itself enforces
    # (see the CheckConstraint on Room) -- reject it here with a clear
    # domain error instead of letting it surface as an opaque IntegrityError.
    new_capacity = changes.get("capacity")
    if new_capacity is not None and new_capacity < room.current_occupancy:
        raise RoomFullError(
            f"cannot set capacity to {new_capacity}: room already has "
            f"{room.current_occupancy} active occupant(s)"
        )
    return hostel_repo.update_room(db, room, changes)


def delete_room(db: Session, room_id) -> bool:
    room = hostel_repo.get_room_by_id(db, room_id)
    if room is None:
        return False
    hostel_repo.delete_room(db, room)  # FK RESTRICT raises IntegrityError if Allocations exist
    return True


# ------------------------------------------------------------------ Allocation


def create_allocation(db: Session, data: AllocationCreate) -> HostelAllocation:
    """
    validate -> check capacity/duplicates -> persist -> bump occupancy
    -> emit hostel.allocated.

    Mirrors the Fee service's pay_fee() shape: every guard runs before any
    write, and the event is only ever published after the allocation (and
    its occupancy side effect) has actually committed.
    """
    student = student_repo.get_by_student_id(db, data.student_id)
    if student is None:
        raise StudentNotFoundError(f"student '{data.student_id}' not found")

    room = hostel_repo.get_room_by_id(db, data.room_id)
    if room is None:
        raise RoomNotFoundError(f"room '{data.room_id}' not found")

    if room.current_occupancy >= room.capacity:
        raise RoomFullError(f"room '{room.room_number}' is at full capacity ({room.capacity})")

    existing = hostel_repo.get_active_allocation_for_student(db, student.id)
    if existing is not None:
        raise DuplicateActiveAllocationError(
            f"student '{data.student_id}' already has an active hostel allocation"
        )

    allocation = hostel_repo.create_allocation(db, student_pk=student.id, room_pk=room.id)
    room = hostel_repo.increment_occupancy(db, room)

    hostel = hostel_repo.get_hostel_by_id(db, room.hostel_id)

    # Post-commit, best-effort publish to Person B's automation backbone --
    # same Critical Event Rule as fee.paid: never publish before the
    # commit, and a failure here must never look like the allocation failed.
    publish(
        db,
        event_type="hostel.allocated",
        aggregate_id=str(allocation.id),
        student_id=student.student_id,
        data={
            "allocation_id": str(allocation.id),
            "student_id": student.student_id,
            "hostel_code": hostel.hostel_code if hostel else None,
            "room_id": str(room.id),
            "room_number": room.room_number,
            "allocated_at": allocation.created_at.isoformat(),
        },
    )

    return allocation


def get_allocation(db: Session, allocation_id) -> HostelAllocation | None:
    return hostel_repo.get_allocation_by_id(db, allocation_id)


def list_allocations(
    db: Session, *, student_id: str | None = None, room_id=None
) -> list[HostelAllocation]:
    student_pk = None
    if student_id is not None:
        student = student_repo.get_by_student_id(db, student_id)
        if student is None:
            raise StudentNotFoundError(f"student '{student_id}' not found")
        student_pk = student.id
    return hostel_repo.list_allocations(db, student_pk=student_pk, room_pk=room_id)


_ALLOWED_TRANSITIONS = {
    AllocationStatus.ACTIVE: {AllocationStatus.VACATED, AllocationStatus.CANCELLED},
}


def update_allocation(db: Session, allocation_id, data: AllocationUpdate) -> HostelAllocation | None:
    """
    The only mutation an allocation supports post-creation is a status
    transition (ACTIVE -> VACATED/CANCELLED); student_id/room_id are
    immutable. On a transition out of ACTIVE, the room's occupancy is
    decremented in the same operation so it never drifts from the actual
    set of ACTIVE allocations.
    """
    allocation = hostel_repo.get_allocation_by_id(db, allocation_id)
    if allocation is None:
        return None

    changes = data.model_dump(exclude_unset=True)
    if not changes or changes.get("status") is None:
        return allocation

    new_status = changes["status"]
    allowed = _ALLOWED_TRANSITIONS.get(allocation.status, set())
    if new_status not in allowed:
        raise InvalidAllocationStateTransitionError(
            f"cannot transition allocation from {allocation.status.value} to {new_status.value}"
        )

    allocation = hostel_repo.set_allocation_status(db, allocation, new_status)

    room = hostel_repo.get_room_by_id(db, allocation.room_id)
    if room is not None:
        hostel_repo.decrement_occupancy(db, room)

    return allocation


def delete_allocation(db: Session, allocation_id) -> bool | None:
    """Returns True if deleted, False if not found, raises if the
    allocation is still ACTIVE (must be vacated/cancelled first so the
    room's occupancy count is never left out of sync)."""
    allocation = hostel_repo.get_allocation_by_id(db, allocation_id)
    if allocation is None:
        return False
    if allocation.status == AllocationStatus.ACTIVE:
        raise InvalidAllocationStateTransitionError(
            "cannot delete an ACTIVE allocation -- vacate or cancel it first"
        )
    hostel_repo.delete_allocation(db, allocation)
    return True
