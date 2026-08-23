// Typed convenience wrappers over `apiFetch` (lib/api.ts) for the
// backend domains this portal needs. Everything here still goes through
// the single central client — these are just typed shortcuts.

import { apiFetch } from "./api";
import type {
  Admission,
  AdmissionStatus,
  Allocation,
  AllocationStatus,
  AttendanceRecord,
  AttendanceStatus,
  CurrentUser,
  Exam,
  Fee,
  Hostel,
  Registration,
  Room,
  StudentRead,
} from "./types";

export function getCurrentUser(): Promise<CurrentUser> {
  return apiFetch("/auth/me");
}

// GET /students/me — resolves the logged-in STUDENT's own record from the
// JWT identity server-side. Never accepts a student_id from the client.
export function getOwnStudent(): Promise<StudentRead> {
  return apiFetch("/students/me");
}

// GET /students/{student_id} — student_id is the human-readable code
// (e.g. "STU2026001"), not the internal UUID. Staff-only in practice per
// backend RBAC (a STUDENT caller is only allowed through for their own
// code — prefer getOwnStudent() for "my own record").
export function getStudent(studentCode: string): Promise<StudentRead> {
  return apiFetch(`/students/${encodeURIComponent(studentCode)}`);
}

// Staff-only per backend RBAC (ADMIN/FACULTY/ACCOUNTS/WARDEN/EXAM_OFFICER).
export function listStudents(): Promise<StudentRead[]> {
  return apiFetch("/students");
}

export function listAttendance(
  params: { student_id?: string; subject?: string } = {}
): Promise<AttendanceRecord[]> {
  const qs = new URLSearchParams();
  if (params.student_id) qs.set("student_id", params.student_id);
  if (params.subject) qs.set("subject", params.subject);
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return apiFetch(`/attendance/records${suffix}`);
}

// Staff-only per backend RBAC (ADMIN/FACULTY).
export function createAttendanceRecord(payload: {
  student_id: string; // human-readable code
  subject: string;
  session_date: string; // YYYY-MM-DD
  status: AttendanceStatus;
  marked_by?: string;
}): Promise<AttendanceRecord> {
  return apiFetch("/attendance/records", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listHostelAllocations(
  params: { student_id?: string } = {}
): Promise<Allocation[]> {
  const qs = new URLSearchParams();
  if (params.student_id) qs.set("student_id", params.student_id);
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return apiFetch(`/hostel/allocations${suffix}`);
}

export function listRooms(): Promise<Room[]> {
  return apiFetch("/hostel/rooms");
}

export function listHostels(): Promise<Hostel[]> {
  return apiFetch("/hostel/hostels");
}

// Staff-only per backend RBAC (ADMIN/WARDEN — see app/api/hostel.py
// _FACILITY_STAFF). Fails 409 if the room is full or the student already
// has an ACTIVE allocation (see app/services/hostel.py create_allocation).
export function createHostelAllocation(payload: {
  student_id: string; // human-readable code, resolved to the FK server-side
  room_id: string;
}): Promise<Allocation> {
  return apiFetch("/hostel/allocations", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// Staff-only per backend RBAC. The only allowed transition out of ACTIVE
// is VACATED or CANCELLED (see app/services/hostel.py _ALLOWED_TRANSITIONS)
// — this also decrements the room's current_occupancy server-side.
export function updateHostelAllocation(
  allocationId: string,
  payload: { status: AllocationStatus }
): Promise<Allocation> {
  return apiFetch(`/hostel/allocations/${encodeURIComponent(allocationId)}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function listExams(): Promise<Exam[]> {
  return apiFetch("/examinations");
}

export function listExamRegistrations(
  examCode: string,
  params: { student_id?: string } = {}
): Promise<Registration[]> {
  const qs = new URLSearchParams();
  if (params.student_id) qs.set("student_id", params.student_id);
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return apiFetch(`/examinations/${encodeURIComponent(examCode)}/registrations${suffix}`);
}

// Staff-only per backend RBAC (ADMIN/EXAM_OFFICER — see app/api/examinations.py
// _EXAM_STAFF). This is the real "approve registration" action — there is
// no separate approval status; creating the registration IS the approval.
// Fails 409 if the student is already registered for this exam.
export function registerForExam(
  examCode: string,
  payload: { student_id: string }
): Promise<Registration> {
  return apiFetch(`/examinations/${encodeURIComponent(examCode)}/register`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// Staff-only per backend RBAC (ADMIN/EXAM_OFFICER). Reverses a registration
// (e.g. entered in error) — no confirmation state, a 204 means it's gone.
export function deleteExamRegistration(
  examCode: string,
  registrationId: string
): Promise<null> {
  return apiFetch(
    `/examinations/${encodeURIComponent(examCode)}/registrations/${encodeURIComponent(registrationId)}`,
    { method: "DELETE" }
  );
}

// GET /fees/me — the logged-in STUDENT's own fees only. student_id is
// resolved server-side from the JWT identity, never supplied by the client.
export function listOwnFees(): Promise<Fee[]> {
  return apiFetch("/fees/me");
}

// Staff-only per backend RBAC (ADMIN/ACCOUNTS) — every fee record, no
// per-student filter (see API_CONTRACT.md).
export function listFees(): Promise<Fee[]> {
  return apiFetch("/fees");
}

// Staff-only per backend RBAC (ADMIN/ACCOUNTS/STUDENT-owns-own-fee).
// Commits the fee to PAID and, only after that commit succeeds, publishes
// the fee.paid domain event — see API_CONTRACT.md "Pay Fee".
export function payFee(
  feeId: string,
  payload: { payment_reference: string }
): Promise<Fee> {
  return apiFetch(`/fees/${encodeURIComponent(feeId)}/pay`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// ADMIN-only per backend RBAC — admissions are a back-office workflow,
// no student self-service (see API_CONTRACT.md).
export function listAdmissions(): Promise<Admission[]> {
  return apiFetch("/admissions");
}

// ADMIN-only. Setting status to "APPROVED" auto-creates/links the Student
// record server-side — that's a backend side effect, not something this
// call performs itself (see API_CONTRACT.md "Update Admission").
export function updateAdmission(
  applicationNumber: string,
  payload: Partial<{
    applicant_name: string;
    applicant_email: string;
    department: string;
    course: string;
    enrollment_year: number;
    admission_type: string;
    status: AdmissionStatus;
  }>
): Promise<Admission> {
  return apiFetch(`/admissions/${encodeURIComponent(applicationNumber)}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}
