"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { LoadingState, ErrorState } from "./portal-ui";
import { useAuthGuard, logout } from "../lib/auth";
import {
  listStudents,
  listAdmissions,
  listFees,
  listRooms,
  listHostels,
  listExams,
  listExamRegistrations,
  updateAdmission,
} from "../lib/services";
import { ApiError } from "../lib/api";
import type { Admission, Exam, Fee, Hostel, Registration, Room, StudentRead } from "../lib/types";

// Same 4-tab layout as the rest of the staff portals (components/staff-portal.tsx)
// — this file only owns the "admin" tab's content and data.
const NAV = [
  { key: "admin", label: "Admin", href: "/admin/dashboard" },
  { key: "accounts", label: "Accounts", href: "/accounts/dashboard" },
  { key: "warden", label: "Warden", href: "/warden/dashboard" },
  { key: "exam", label: "Examinations", href: "/exam/dashboard" },
];

type DataState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | {
      status: "ready";
      students: StudentRead[];
      admissions: Admission[];
      fees: Fee[];
      hostels: Hostel[];
      rooms: Room[];
      exams: Exam[];
      registrationsByExam: Map<string, Registration[]>;
    };

export function AdminPortal() {
  const router = useRouter();
  const guard = useAuthGuard(["admin"]);

  const [state, setState] = useState<DataState>({ status: "loading" });
  const [approvingId, setApprovingId] = useState<string | null>(null);
  const [approveError, setApproveError] = useState<string | null>(null);

  function load() {
    setState({ status: "loading" });
    Promise.all([listStudents(), listAdmissions(), listFees(), listRooms(), listHostels(), listExams()])
      .then(async ([students, admissions, fees, rooms, hostels, exams]) => {
        // No single endpoint reports registrations across every exam, so
        // this fetches each exam's own registrations (existing per-exam
        // endpoint, already granted to ADMIN — see API_CONTRACT.md) and
        // aggregates client-side rather than adding a new backend route.
        const registrationLists = await Promise.all(
          exams.map((exam) => listExamRegistrations(exam.exam_code))
        );
        const registrationsByExam = new Map(
          exams.map((exam, i) => [exam.exam_code, registrationLists[i]])
        );
        setState({
          status: "ready",
          students,
          admissions,
          fees,
          hostels,
          rooms,
          exams,
          registrationsByExam,
        });
      })
      .catch((err) =>
        setState({
          status: "error",
          message: err instanceof ApiError ? err.message : "Failed to load dashboard data.",
        })
      );
  }

  useEffect(() => {
    if (guard.status === "ready") load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [guard.status]);

  async function approveAdmission(applicationNumber: string) {
    setApprovingId(applicationNumber);
    setApproveError(null);
    try {
      await updateAdmission(applicationNumber, { status: "APPROVED" });
      load();
    } catch (err) {
      setApproveError(
        err instanceof ApiError ? err.message : "Failed to approve admission."
      );
    } finally {
      setApprovingId(null);
    }
  }

  const students = state.status === "ready" ? state.students : [];
  const admissions = state.status === "ready" ? state.admissions : [];
  const fees = state.status === "ready" ? state.fees : [];
  const hostels = state.status === "ready" ? state.hostels : [];
  const rooms = state.status === "ready" ? state.rooms : [];
  const exams = state.status === "ready" ? state.exams : [];
  const registrationsByExam = state.status === "ready" ? state.registrationsByExam : new Map<string, Registration[]>();

  const totalFeeAmount = fees.reduce((sum, f) => sum + Number(f.amount), 0);
  const collectedAmount = fees
    .filter((f) => f.status === "PAID")
    .reduce((sum, f) => sum + Number(f.amount), 0);
  const collectionPct = totalFeeAmount > 0 ? Math.round((collectedAmount / totalFeeAmount) * 100) : 0;

  const pendingAdmissions = admissions
    .filter((a) => a.status === "APPLIED" || a.status === "UNDER_REVIEW")
    .sort((a, b) => (a.application_date < b.application_date ? -1 : 1));

  const overdueFeeCount = fees.filter((f) => f.status === "OVERDUE").length;

  const recentApprovedAdmissions = admissions
    .filter((a) => a.status === "APPROVED")
    .sort((a, b) => (a.updated_at < b.updated_at ? 1 : -1))
    .slice(0, 5);

  const totalBeds = rooms.reduce((sum, r) => sum + r.capacity, 0);
  const occupiedBeds = rooms.reduce((sum, r) => sum + r.current_occupancy, 0);
  const occupancyPct = totalBeds > 0 ? Math.round((occupiedBeds / totalBeds) * 100) : 0;

  const totalRegistrations = Array.from(registrationsByExam.values()).reduce(
    (sum, regs) => sum + regs.length,
    0
  );

  const roomsByHostel = new Map<string, Room[]>();
  for (const room of rooms) {
    const list = roomsByHostel.get(room.hostel_id) ?? [];
    list.push(room);
    roomsByHostel.set(room.hostel_id, list);
  }

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-slate-800">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-5">
          <div>
            <h1 className="text-2xl font-bold">
              Campus<span className="text-blue-500">Flow</span> AI
            </h1>
            <p className="text-sm text-slate-400">Admin Portal</p>
          </div>

          <button
            onClick={() => logout(router)}
            className="rounded-lg border border-slate-700 px-4 py-2 text-sm hover:bg-slate-800"
          >
            Logout
          </button>
        </div>
      </header>

      <nav className="border-b border-slate-800 bg-slate-900/50">
        <div className="mx-auto flex max-w-7xl gap-2 overflow-x-auto px-6 py-3">
          {NAV.map((item) => (
            <Link
              key={item.key}
              href={item.href}
              className={`whitespace-nowrap rounded-lg px-4 py-2 text-sm font-medium ${
                item.key === "admin"
                  ? "bg-blue-600 text-white"
                  : "text-slate-300 hover:bg-slate-800"
              }`}
            >
              {item.label}
            </Link>
          ))}
        </div>
      </nav>

      <section className="mx-auto max-w-7xl px-6 py-10">
        <p className="text-slate-400">Institutional overview</p>
        <h2 className="mt-1 text-3xl font-bold">Campus Command Center</h2>

        {guard.status !== "ready" && <LoadingState label="Checking your session..." />}

        {guard.status === "ready" && state.status === "loading" && (
          <LoadingState label="Loading dashboard data..." />
        )}

        {guard.status === "ready" && state.status === "error" && (
          <ErrorState message={state.message} onRetry={load} />
        )}

        {guard.status === "ready" && state.status === "ready" && (
          <>
            <div className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              <Card label="Active Students" value={String(students.length)} note="Total student records" />
              <Card
                label="Fee Collection"
                value={`${collectionPct}%`}
                note={`₹${collectedAmount.toLocaleString("en-IN")} of ₹${totalFeeAmount.toLocaleString("en-IN")} collected`}
                color="text-emerald-400"
              />
              <Card
                label="Pending Admissions"
                value={String(pendingAdmissions.length)}
                note="Awaiting review or approval"
                color="text-amber-300"
              />
              <Card
                label="Overdue Fees"
                value={String(overdueFeeCount)}
                note="Fee records past due date"
                color="text-red-400"
              />
              <Card
                label="Hostel Occupancy"
                value={totalBeds > 0 ? `${occupancyPct}%` : "—"}
                note={totalBeds > 0 ? `${occupiedBeds} of ${totalBeds} beds allocated` : "No rooms configured yet"}
                color="text-violet-300"
              />
              <Card
                label="Exam Registrations"
                value={String(totalRegistrations)}
                note={exams.length > 0 ? `Across ${exams.length} examination${exams.length === 1 ? "" : "s"}` : "No examinations scheduled yet"}
              />
            </div>

            <div className="mt-8 grid gap-6 lg:grid-cols-3">
              <article className="rounded-2xl border border-slate-800 bg-slate-900 p-6 lg:col-span-2">
                <h3 className="text-xl font-semibold">Admissions awaiting approval</h3>
                <p className="mt-2 text-sm text-slate-400">
                  Approving an admission provisions the linked Student record.
                </p>

                {approveError && (
                  <p className="mt-3 rounded-lg bg-red-500/10 px-4 py-2 text-sm text-red-300">
                    {approveError}
                  </p>
                )}

                {pendingAdmissions.length === 0 ? (
                  <p className="mt-5 text-sm text-slate-500">No admissions are pending review.</p>
                ) : (
                  <ul className="mt-5 space-y-3">
                    {pendingAdmissions.slice(0, 5).map((admission) => (
                      <li
                        key={admission.id}
                        className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-slate-800/70 p-4"
                      >
                        <div>
                          <p className="font-medium">{admission.applicant_name}</p>
                          <p className="text-xs text-slate-400">
                            {admission.application_number} · {admission.department} · {admission.course}
                          </p>
                          <p className="mt-1 text-xs text-slate-500">Status: {admission.status}</p>
                        </div>
                        <button
                          disabled={approvingId === admission.application_number}
                          onClick={() => approveAdmission(admission.application_number)}
                          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold hover:bg-blue-700 disabled:bg-slate-700"
                        >
                          {approvingId === admission.application_number ? "Approving..." : "Approve"}
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </article>

              <article className="rounded-2xl border border-slate-800 bg-slate-900 p-6">
                <h3 className="font-semibold">Recently approved</h3>
                {recentApprovedAdmissions.length === 0 ? (
                  <p className="mt-4 text-sm text-slate-500">No approvals yet.</p>
                ) : (
                  <ul className="mt-4 space-y-4 text-sm text-slate-300">
                    {recentApprovedAdmissions.map((admission) => (
                      <li key={admission.id}>
                        🟢 {admission.applicant_name} ({admission.application_number})
                      </li>
                    ))}
                  </ul>
                )}
              </article>
            </div>

            <div className="mt-8 grid gap-6 lg:grid-cols-2">
              <article className="rounded-2xl border border-slate-800 bg-slate-900 p-6">
                <h3 className="font-semibold">Hostel occupancy by hostel</h3>
                {hostels.length === 0 ? (
                  <p className="mt-4 text-sm text-slate-500">No hostels configured yet.</p>
                ) : (
                  <ul className="mt-4 space-y-3 text-sm">
                    {hostels.map((hostel) => {
                      const hostelRooms = roomsByHostel.get(hostel.id) ?? [];
                      const capacity = hostelRooms.reduce((sum, r) => sum + r.capacity, 0);
                      const occupied = hostelRooms.reduce((sum, r) => sum + r.current_occupancy, 0);
                      return (
                        <li key={hostel.id} className="flex items-center justify-between rounded-xl bg-slate-800/70 px-4 py-3">
                          <span className="text-slate-300">{hostel.name}</span>
                          <span className="text-slate-400">
                            {occupied}/{capacity} beds
                          </span>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </article>

              <article className="rounded-2xl border border-slate-800 bg-slate-900 p-6">
                <h3 className="font-semibold">Registrations by examination</h3>
                {exams.length === 0 ? (
                  <p className="mt-4 text-sm text-slate-500">No examinations scheduled yet.</p>
                ) : (
                  <ul className="mt-4 space-y-3 text-sm">
                    {exams.map((exam) => (
                      <li key={exam.id} className="flex items-center justify-between rounded-xl bg-slate-800/70 px-4 py-3">
                        <div>
                          <p className="text-slate-300">{exam.subject}</p>
                          <p className="text-xs text-slate-500">{exam.exam_code} · {exam.status}</p>
                        </div>
                        <span className="text-slate-400">
                          {(registrationsByExam.get(exam.exam_code) ?? []).length} registered
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </article>
            </div>
          </>
        )}
      </section>
    </main>
  );
}

function Card({
  label,
  value,
  note,
  color = "text-blue-400",
}: {
  label: string;
  value: string;
  note: string;
  color?: string;
}) {
  return (
    <article className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
      <p className="text-sm text-slate-400">{label}</p>
      <p className={`mt-3 text-3xl font-bold ${color}`}>{value}</p>
      <p className="mt-2 text-sm text-slate-500">{note}</p>
    </article>
  );
}
