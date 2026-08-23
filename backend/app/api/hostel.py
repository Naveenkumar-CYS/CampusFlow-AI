import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.rbac import (
    Role,
    enforce_own_student_filter,
    enforce_own_student_record,
    require_roles,
)
from app.db.session import get_db
from app.schemas.auth import CurrentUser
from app.schemas.hostel import (
    AllocationCreate,
    AllocationRead,
    AllocationUpdate,
    HostelCreate,
    HostelRead,
    HostelUpdate,
    RoomCreate,
    RoomRead,
    RoomUpdate,
)
from app.services import hostel as hostel_service

hostels_router = APIRouter(prefix="/hostel/hostels", tags=["hostel"])
rooms_router = APIRouter(prefix="/hostel/rooms", tags=["hostel"])
allocations_router = APIRouter(prefix="/hostel/allocations", tags=["hostel"])

_FACILITY_STAFF = {Role.ADMIN, Role.WARDEN}
# Hostel/room listings are general campus facility info (not tied to a
# specific student), so any authenticated role may read them.
_ANY_AUTHENTICATED = {
    Role.ADMIN, Role.WARDEN, Role.STUDENT, Role.FACULTY, Role.ACCOUNTS, Role.EXAM_OFFICER,
}


# --------------------------------------------------------------------- Hostel


@hostels_router.post(
    "", response_model=HostelRead, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(*_FACILITY_STAFF))],
)
def create_hostel(payload: HostelCreate, db: Session = Depends(get_db)) -> HostelRead:
    try:
        return hostel_service.create_hostel(db, payload)
    except hostel_service.DuplicateHostelError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@hostels_router.get(
    "/{hostel_code}", response_model=HostelRead,
    dependencies=[Depends(require_roles(*_ANY_AUTHENTICATED))],
)
def get_hostel(hostel_code: str, db: Session = Depends(get_db)) -> HostelRead:
    hostel = hostel_service.get_hostel(db, hostel_code)
    if hostel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hostel not found")
    return hostel


@hostels_router.get(
    "", response_model=list[HostelRead],
    dependencies=[Depends(require_roles(*_ANY_AUTHENTICATED))],
)
def list_hostels(db: Session = Depends(get_db)) -> list[HostelRead]:
    return hostel_service.list_hostels(db)


@hostels_router.patch(
    "/{hostel_code}", response_model=HostelRead,
    dependencies=[Depends(require_roles(*_FACILITY_STAFF))],
)
def update_hostel(hostel_code: str, payload: HostelUpdate, db: Session = Depends(get_db)) -> HostelRead:
    hostel = hostel_service.update_hostel(db, hostel_code, payload)
    if hostel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hostel not found")
    return hostel


@hostels_router.delete(
    "/{hostel_code}", status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(*_FACILITY_STAFF))],
)
def delete_hostel(hostel_code: str, db: Session = Depends(get_db)) -> None:
    try:
        deleted = hostel_service.delete_hostel(db, hostel_code)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete hostel with existing rooms",
        ) from exc
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hostel not found")


# ------------------------------------------------------------------------ Room


@rooms_router.post(
    "", response_model=RoomRead, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(*_FACILITY_STAFF))],
)
def create_room(payload: RoomCreate, db: Session = Depends(get_db)) -> RoomRead:
    try:
        return hostel_service.create_room(db, payload)
    except hostel_service.HostelNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except hostel_service.DuplicateRoomError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@rooms_router.get(
    "/{room_id}", response_model=RoomRead,
    dependencies=[Depends(require_roles(*_ANY_AUTHENTICATED))],
)
def get_room(room_id: uuid.UUID, db: Session = Depends(get_db)) -> RoomRead:
    room = hostel_service.get_room(db, room_id)
    if room is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
    return room


@rooms_router.get(
    "", response_model=list[RoomRead],
    dependencies=[Depends(require_roles(*_ANY_AUTHENTICATED))],
)
def list_rooms(hostel_code: str | None = None, db: Session = Depends(get_db)) -> list[RoomRead]:
    try:
        return hostel_service.list_rooms(db, hostel_code=hostel_code)
    except hostel_service.HostelNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@rooms_router.patch(
    "/{room_id}", response_model=RoomRead,
    dependencies=[Depends(require_roles(*_FACILITY_STAFF))],
)
def update_room(room_id: uuid.UUID, payload: RoomUpdate, db: Session = Depends(get_db)) -> RoomRead:
    try:
        room = hostel_service.update_room(db, room_id, payload)
    except hostel_service.RoomFullError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if room is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
    return room


@rooms_router.delete(
    "/{room_id}", status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(*_FACILITY_STAFF))],
)
def delete_room(room_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    try:
        deleted = hostel_service.delete_room(db, room_id)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete room with existing allocations",
        ) from exc
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")


# ------------------------------------------------------------------ Allocation


@allocations_router.post(
    "", response_model=AllocationRead, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(*_FACILITY_STAFF))],
)
def create_allocation(payload: AllocationCreate, db: Session = Depends(get_db)) -> AllocationRead:
    try:
        return hostel_service.create_allocation(db, payload)
    except hostel_service.StudentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except hostel_service.RoomNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except hostel_service.RoomFullError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except hostel_service.DuplicateActiveAllocationError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@allocations_router.get("/{allocation_id}", response_model=AllocationRead)
def get_allocation(
    allocation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(*_FACILITY_STAFF, Role.STUDENT)),
) -> AllocationRead:
    allocation = hostel_service.get_allocation(db, allocation_id)
    if allocation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Allocation not found")
    enforce_own_student_record(
        current_user, db, staff_roles=_FACILITY_STAFF, target_student_pk=allocation.student_id
    )
    return allocation


@allocations_router.get("", response_model=list[AllocationRead])
def list_allocations(
    student_id: str | None = None,
    room_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(*_FACILITY_STAFF, Role.STUDENT)),
) -> list[AllocationRead]:
    enforce_own_student_filter(
        current_user, db, staff_roles=_FACILITY_STAFF, requested_student_code=student_id
    )
    try:
        return hostel_service.list_allocations(db, student_id=student_id, room_id=room_id)
    except hostel_service.StudentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@allocations_router.patch(
    "/{allocation_id}", response_model=AllocationRead,
    dependencies=[Depends(require_roles(*_FACILITY_STAFF))],
)
def update_allocation(
    allocation_id: uuid.UUID, payload: AllocationUpdate, db: Session = Depends(get_db)
) -> AllocationRead:
    try:
        allocation = hostel_service.update_allocation(db, allocation_id, payload)
    except hostel_service.InvalidAllocationStateTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if allocation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Allocation not found")
    return allocation


@allocations_router.delete(
    "/{allocation_id}", status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(*_FACILITY_STAFF))],
)
def delete_allocation(allocation_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    try:
        deleted = hostel_service.delete_allocation(db, allocation_id)
    except hostel_service.InvalidAllocationStateTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Allocation not found")
