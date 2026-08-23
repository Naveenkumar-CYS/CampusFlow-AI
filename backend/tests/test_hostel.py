"""
Automated tests for the Hostel service: Hostel/Room/Allocation CRUD,
the allocation business logic (capacity, duplicate-active-allocation,
invalid student/room guards), the vacate/cancel state transition, and
event emission for a real hostel.allocated event via Person B's
automation backbone.

Same conventions as test_fee.py / test_api.py: runs against the real
dev DB from .env, random suffixes so repeated runs don't collide.
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _suffix() -> str:
    return uuid.uuid4().hex[:6].upper()


def _make_student() -> str:
    sid = f"STUH{_suffix()}"
    resp = client.post(
        "/students",
        json={
            "student_id": sid,
            "name": "Hostel Test Student",
            "email": f"{sid.lower()}@example.edu",
            "department": "CSE",
            "course": "B.Tech",
            "enrollment_year": 2026,
        },
    )
    assert resp.status_code == 201
    return sid


def _make_hostel() -> str:
    code = f"HOS{_suffix()}"
    resp = client.post("/hostel/hostels", json={"hostel_code": code, "name": "Test Hostel"})
    assert resp.status_code == 201
    return code


def _make_room(hostel_code: str, capacity: int = 2) -> dict:
    resp = client.post(
        "/hostel/rooms",
        json={"hostel_code": hostel_code, "room_number": f"R{_suffix()}", "capacity": capacity},
    )
    assert resp.status_code == 201
    return resp.json()


# ------------------------------------------------------------------- Hostel


def test_create_get_list_hostel():
    code = f"HOS{_suffix()}"
    resp = client.post("/hostel/hostels", json={"hostel_code": code, "name": "Sunrise Hostel"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["hostel_code"] == code

    assert client.get(f"/hostel/hostels/{code}").status_code == 200
    assert any(h["hostel_code"] == code for h in client.get("/hostel/hostels").json())


def test_duplicate_hostel_code_rejected():
    code = f"HOS{_suffix()}"
    payload = {"hostel_code": code, "name": "Dup Hostel"}
    assert client.post("/hostel/hostels", json=payload).status_code == 201
    assert client.post("/hostel/hostels", json=payload).status_code == 409


def test_get_missing_hostel_404():
    assert client.get("/hostel/hostels/HOSTEL_DOES_NOT_EXIST").status_code == 404


def test_update_delete_hostel():
    code = _make_hostel()
    resp = client.patch(f"/hostel/hostels/{code}", json={"name": "Renamed Hostel"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed Hostel"

    assert client.delete(f"/hostel/hostels/{code}").status_code == 204
    assert client.get(f"/hostel/hostels/{code}").status_code == 404


def test_delete_hostel_with_rooms_blocked():
    code = _make_hostel()
    _make_room(code)
    resp = client.delete(f"/hostel/hostels/{code}")
    assert resp.status_code == 409


# --------------------------------------------------------------------- Room


def test_create_get_list_room():
    code = _make_hostel()
    room = _make_room(code, capacity=3)
    assert room["capacity"] == 3
    assert room["current_occupancy"] == 0

    assert client.get(f"/hostel/rooms/{room['id']}").status_code == 200
    assert any(r["id"] == room["id"] for r in client.get("/hostel/rooms").json())
    assert any(
        r["id"] == room["id"]
        for r in client.get(f"/hostel/rooms?hostel_code={code}").json()
    )


def test_room_for_unknown_hostel_404():
    resp = client.post(
        "/hostel/rooms",
        json={"hostel_code": "HOSTEL_DOES_NOT_EXIST", "room_number": "R1", "capacity": 2},
    )
    assert resp.status_code == 404


def test_duplicate_room_number_in_hostel_rejected():
    code = _make_hostel()
    room_number = f"R{_suffix()}"
    payload = {"hostel_code": code, "room_number": room_number, "capacity": 2}
    assert client.post("/hostel/rooms", json=payload).status_code == 201
    assert client.post("/hostel/rooms", json=payload).status_code == 409


def test_get_missing_room_404():
    assert client.get(f"/hostel/rooms/{uuid.uuid4()}").status_code == 404


def test_update_delete_room():
    code = _make_hostel()
    room = _make_room(code, capacity=2)
    resp = client.patch(f"/hostel/rooms/{room['id']}", json={"capacity": 4})
    assert resp.status_code == 200
    assert resp.json()["capacity"] == 4

    assert client.delete(f"/hostel/rooms/{room['id']}").status_code == 204
    assert client.get(f"/hostel/rooms/{room['id']}").status_code == 404


# --------------------------------------------------------------- Allocation


def test_allocation_success_updates_occupancy():
    sid = _make_student()
    code = _make_hostel()
    room = _make_room(code, capacity=2)

    resp = client.post("/hostel/allocations", json={"student_id": sid, "room_id": room["id"]})
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "ACTIVE"
    assert body["vacated_at"] is None

    room_after = client.get(f"/hostel/rooms/{room['id']}").json()
    assert room_after["current_occupancy"] == 1


def test_allocation_invalid_student_404():
    code = _make_hostel()
    room = _make_room(code)
    resp = client.post(
        "/hostel/allocations", json={"student_id": "STU_DOES_NOT_EXIST", "room_id": room["id"]}
    )
    assert resp.status_code == 404


def test_allocation_invalid_room_404():
    sid = _make_student()
    resp = client.post(
        "/hostel/allocations", json={"student_id": sid, "room_id": str(uuid.uuid4())}
    )
    assert resp.status_code == 404


def test_allocation_capacity_exceeded_rejected():
    code = _make_hostel()
    room = _make_room(code, capacity=1)
    sid1 = _make_student()
    sid2 = _make_student()

    assert client.post(
        "/hostel/allocations", json={"student_id": sid1, "room_id": room["id"]}
    ).status_code == 201

    resp = client.post("/hostel/allocations", json={"student_id": sid2, "room_id": room["id"]})
    assert resp.status_code == 409


def test_duplicate_active_allocation_rejected():
    code = _make_hostel()
    room1 = _make_room(code, capacity=2)
    room2 = _make_room(code, capacity=2)
    sid = _make_student()

    assert client.post(
        "/hostel/allocations", json={"student_id": sid, "room_id": room1["id"]}
    ).status_code == 201

    resp = client.post("/hostel/allocations", json={"student_id": sid, "room_id": room2["id"]})
    assert resp.status_code == 409


def test_vacate_allocation_frees_capacity_and_allows_reallocation():
    code = _make_hostel()
    room = _make_room(code, capacity=1)
    sid = _make_student()

    alloc = client.post(
        "/hostel/allocations", json={"student_id": sid, "room_id": room["id"]}
    ).json()

    resp = client.patch(f"/hostel/allocations/{alloc['id']}", json={"status": "VACATED"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "VACATED"
    assert resp.json()["vacated_at"] is not None

    room_after = client.get(f"/hostel/rooms/{room['id']}").json()
    assert room_after["current_occupancy"] == 0

    # Student can now be allocated again (no more active allocation),
    # and the now-freed room can be reused.
    resp2 = client.post("/hostel/allocations", json={"student_id": sid, "room_id": room["id"]})
    assert resp2.status_code == 201


def test_revacating_already_vacated_allocation_rejected():
    code = _make_hostel()
    room = _make_room(code)
    sid = _make_student()
    alloc = client.post(
        "/hostel/allocations", json={"student_id": sid, "room_id": room["id"]}
    ).json()

    assert client.patch(
        f"/hostel/allocations/{alloc['id']}", json={"status": "VACATED"}
    ).status_code == 200
    resp = client.patch(f"/hostel/allocations/{alloc['id']}", json={"status": "VACATED"})
    assert resp.status_code == 409


def test_delete_active_allocation_blocked_then_allowed_after_vacate():
    code = _make_hostel()
    room = _make_room(code)
    sid = _make_student()
    alloc = client.post(
        "/hostel/allocations", json={"student_id": sid, "room_id": room["id"]}
    ).json()

    assert client.delete(f"/hostel/allocations/{alloc['id']}").status_code == 409

    client.patch(f"/hostel/allocations/{alloc['id']}", json={"status": "VACATED"})
    assert client.delete(f"/hostel/allocations/{alloc['id']}").status_code == 204
    assert client.get(f"/hostel/allocations/{alloc['id']}").status_code == 404


def test_get_missing_allocation_404():
    assert client.get(f"/hostel/allocations/{uuid.uuid4()}").status_code == 404


# ------------------------------------------------- Event emission (Phase 13)


def test_hostel_allocated_triggers_real_automation_event():
    """
    A real POST /hostel/allocations must reach Person B's EventConsumer
    via the registered hostel.allocated adapter and produce an Execution
    row -- same integration pattern as test_fee.py's fee.paid test.
    """
    sid = _make_student()
    code = _make_hostel()
    room = _make_room(code)

    resp = client.post("/hostel/allocations", json={"student_id": sid, "room_id": room["id"]})
    assert resp.status_code == 201

    from app.db.session import SessionLocal
    from app.repositories import execution as execution_repo

    db = SessionLocal()
    try:
        executions = execution_repo.list_all(db, limit=5)
        assert any(e.status in ("success", "failed") for e in executions), (
            "expected at least one recent automation Execution row after a "
            "real hostel.allocated event"
        )
    finally:
        db.close()


def test_event_not_emitted_after_failed_allocation():
    """
    A failed allocation (capacity exceeded) must not increment occupancy
    or leave any trace of a successful allocation -- i.e. no event-worthy
    state change happened. We assert this indirectly: occupancy stays at
    the room's capacity (no over-allocation) and no new ACTIVE allocation
    is created for the rejected student.
    """
    code = _make_hostel()
    room = _make_room(code, capacity=1)
    sid1 = _make_student()
    sid2 = _make_student()

    client.post("/hostel/allocations", json={"student_id": sid1, "room_id": room["id"]})
    resp = client.post("/hostel/allocations", json={"student_id": sid2, "room_id": room["id"]})
    assert resp.status_code == 409

    room_after = client.get(f"/hostel/rooms/{room['id']}").json()
    assert room_after["current_occupancy"] == 1  # unchanged by the failed attempt

    allocations = client.get(f"/hostel/allocations?student_id={sid2}").json()
    assert allocations == []
