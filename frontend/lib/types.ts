// Types mirror the backend Pydantic response schemas exactly
// (see backend/app/schemas/*.py). Keep in sync if those change.

export interface CurrentUser {
  user_id: string;
  email: string;
  role: string; // "student" | "faculty" | "admin" | "accounts" | "warden" | "exam_officer"
}

export interface StudentRead {
  id: string;
  student_id: string; // human-readable code, e.g. "STU2026001"
  name: string;
  email: string;
  department: string;
  course: string;
  enrollment_year: number;
  phone: string | null;
  created_at: string;
  updated_at: string;
}

export type AttendanceStatus = "PRESENT" | "ABSENT" | "LATE" | "EXCUSED";

export interface AttendanceRecord {
  id: string;
  student_id: string; // internal UUID FK, not the human-readable code
  subject: string;
  session_date: string; // ISO date
  status: AttendanceStatus;
  marked_by: string | null;
  created_at: string;
  updated_at: string;
}

export type FeeStatus = "PENDING" | "PAID" | "OVERDUE" | "CANCELLED";

export interface Fee {
  id: string;
  fee_id: string;
  student_id: string;
  fee_type: string;
  amount: string;
  due_date: string;
  status: FeeStatus;
  payment_reference: string | null;
  paid_at: string | null;
}

export type AllocationStatus = "ACTIVE" | "VACATED" | "CANCELLED";

export interface Hostel {
  id: string;
  hostel_code: string;
  name: string;
}

export interface Room {
  id: string;
  hostel_id: string;
  room_number: string;
  capacity: number;
  current_occupancy: number;
}

export interface Allocation {
  id: string;
  student_id: string;
  room_id: string;
  status: AllocationStatus;
  vacated_at: string | null;
  created_at: string;
}

export type ExamStatus = "SCHEDULED" | "COMPLETED" | "CANCELLED";

export interface Exam {
  id: string;
  exam_code: string;
  subject: string;
  scheduled_at: string;
  status: ExamStatus;
}

export interface Registration {
  id: string;
  student_id: string;
  exam_id: string;
  created_at: string;
}

export type AdmissionStatus =
  | "APPLIED"
  | "UNDER_REVIEW"
  | "APPROVED"
  | "REJECTED"
  | "CANCELLED";

export interface Admission {
  id: string;
  application_number: string;
  student_id: string | null; // populated only after status becomes APPROVED
  applicant_name: string;
  applicant_email: string;
  department: string;
  course: string;
  enrollment_year: number;
  application_date: string;
  admission_type: string;
  status: AdmissionStatus;
  created_at: string;
  updated_at: string;
}
