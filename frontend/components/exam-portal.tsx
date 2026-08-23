"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { LoadingState, ErrorState, EmptyState } from "./portal-ui";
import { useAuthGuard, logout } from "../lib/auth";
import {
  deleteExamRegistration,
  listExamRegistrations,
  listExams,
  listStudents,
  registerForExam,
} from "../lib/services";
import { ApiError } from "../lib/api";
import type { Exam, Registration, StudentRead } from "../lib/types";

// Same 4-tab layout as the rest of the staff portals (components/accounts-portal.tsx)
// — this file only owns the "exam" tab's content and data.
const NAV = [
  { key: "admin", label: "Admin", href: "/admin/dashboard" },
  { key: "accounts", label: "Accounts", href: "/accounts/dashboard" },
  { key: "warden", label: "Warden", href: "/warden/dashboard" },
  { key: "exam", label: "Examinations", href: "/exam/dashboard" },
];

type ExamsState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; exams: Exam[]; students: StudentRead[] };

type RegistrationsState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; registrations: Registration[] };

export function ExamPortal() {
  const router = useRouter();
  // EXAM_OFFICER owns exam registration; ADMIN also has staff access to the
  // same /examinations endpoints per backend RBAC (app/api/examinations.py
  // _EXAM_STAFF), so both are allowed in here — same pattern as the other
  // staff portals.
  const guard = useAuthGuard(["exam_officer", "admin"]);

  const [examsState, setExamsState] = useState<ExamsState>({ status: "loading" });
  const [selectedExamCode, setSelectedExamCode] = useState<string | null>(null);
  const [regsState, setRegsState] = useState<RegistrationsState>({ status: "idle" });

  const [selectedStudent, setSelectedStudent] = useState("");
  const [registerError, setRegisterError] = useState<string | null>(null);
  const [registerSubmitting, setRegisterSubmitting] = useState(false);
  const [removingId, setRemovingId] = useState<string | null>(null);

  function loadExams() {
    setExamsState({ status: "loading" });
    Promise.all([listExams(), listStudents()])
      .then(([exams, students]) => {
        setExamsState({ status: "ready", exams, students });
        setSelectedExamCode((current) => current ?? exams[0]?.exam_code ?? null);
      })
      .catch((err) =>
        setExamsState({
          status: "error",
          message: err instanceof ApiError ? err.message : "Failed to load examinations.",
        })
      );
  }

  function loadRegistrations(examCode: string) {
    setRegsState({ status: "loading" });
    listExamRegistrations(examCode)
      .then((registrations) => setRegsState({ status: "ready", registrations }))
      .catch((err) =>
        setRegsState({
          status: "error",
          message: err instanceof ApiError ? err.message : "Failed to load registrations.",
        })
      );
  }

  useEffect(() => {
    if (guard.status === "ready") loadExams();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [guard.status]);

  useEffect(() => {
    if (selectedExamCode) loadRegistrations(selectedExamCode);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedExamCode]);

  const exams = examsState.status === "ready" ? examsState.exams : [];
  const students = examsState.status === "ready" ? examsState.students : [];
  const studentByPk = new Map(students.map((s) => [s.id, s]));
  const selectedExam = exams.find((e) => e.exam_code === selectedExamCode) ?? null;

  const registrations = regsState.status === "ready" ? regsState.registrations : [];
  const registeredStudentPks = new Set(registrations.map((r) => r.student_id));
  const unregisteredStudents = students.filter((s) => !registeredStudentPks.has(s.id));

  const sortedRegistrations = registrations
    .slice()
    .sort((a, b) => (a.created_at < b.created_at ? 1 : -1));

  async function submitRegistration() {
    if (!selectedExamCode || !selectedStudent) {
      setRegisterError("Choose a student to register.");
      return;
    }
    setRegisterSubmitting(true);
    setRegisterError(null);
    try {
      await registerForExam(selectedExamCode, { student_id: selectedStudent });
      setSelectedStudent("");
      loadRegistrations(selectedExamCode);
    } catch (err) {
      setRegisterError(err instanceof ApiError ? err.message : "Failed to register student.");
    } finally {
      setRegisterSubmitting(false);
    }
  }

  async function removeRegistration(registrationId: string) {
    if (!selectedExamCode) return;
    setRemovingId(registrationId);
    try {
      await deleteExamRegistration(selectedExamCode, registrationId);
      loadRegistrations(selectedExamCode);
    } catch {
      // A single failed removal just leaves the row actionable again; the
      // general error state covers systemic failures on next load.
    } finally {
      setRemovingId(null);
    }
  }

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-slate-800">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-5">
          <div>
            <h1 className="text-2xl font-bold">
              Campus<span className="text-blue-500">Flow</span> AI
            </h1>
            <p className="text-sm text-slate-400">Examinations Portal</p>
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
                item.key === "exam"
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
        <p className="text-slate-400">Examination control</p>
        <h2 className="mt-1 text-3xl font-bold">Exam Registration</h2>

        {guard.status !== "ready" && <LoadingState label="Checking your session..." />}

        {guard.status === "ready" && examsState.status === "loading" && (
          <LoadingState label="Loading examinations..." />
        )}

        {guard.status === "ready" && examsState.status === "error" && (
          <ErrorState message={examsState.message} onRetry={loadExams} />
        )}

        {guard.status === "ready" && examsState.status === "ready" && (
          <>
            {exams.length === 0 ? (
              <div className="mt-8">
                <EmptyState message="No examinations have been scheduled yet." />
              </div>
            ) : (
              <>
                <div className="mt-8 max-w-md">
                  <label className="text-sm text-slate-400">Examination</label>
                  <select
                    value={selectedExamCode ?? ""}
                    onChange={(e) => setSelectedExamCode(e.target.value)}
                    className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white"
                  >
                    {exams.map((exam) => (
                      <option key={exam.exam_code} value={exam.exam_code}>
                        {exam.exam_code} — {exam.subject}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="mt-8 grid gap-5 sm:grid-cols-3">
                  <Card
                    label="Registrations"
                    value={regsState.status === "ready" ? String(registrations.length) : "—"}
                    note={selectedExam ? selectedExam.subject : "Selected examination"}
                  />
                  <Card
                    label="Status"
                    value={selectedExam?.status ?? "—"}
                    note={
                      selectedExam
                        ? new Date(selectedExam.scheduled_at).toLocaleString("en-IN")
                        : "Schedule"
                    }
                    color="text-violet-300"
                  />
                  <Card
                    label="Not yet registered"
                    value={String(unregisteredStudents.length)}
                    note="Of all enrolled students"
                    color="text-amber-300"
                  />
                </div>

                <article className="mt-8 max-w-2xl rounded-2xl border border-slate-800 bg-slate-900 p-6">
                  <h3 className="font-semibold">Register a student</h3>
                  <p className="mt-1 text-sm text-slate-400">
                    Registering a student for this examination is the approval — there is no
                    separate review step.
                  </p>

                  {unregisteredStudents.length === 0 ? (
                    <p className="mt-4 text-sm text-slate-500">
                      Every student is already registered for this examination.
                    </p>
                  ) : (
                    <div className="mt-5 flex flex-col gap-3">
                      <select
                        value={selectedStudent}
                        onChange={(e) => setSelectedStudent(e.target.value)}
                        className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white"
                      >
                        <option value="">Select student...</option>
                        {unregisteredStudents.map((s) => (
                          <option key={s.id} value={s.student_id}>
                            {s.name} — {s.student_id}
                          </option>
                        ))}
                      </select>

                      {registerError && <p className="text-xs text-red-400">{registerError}</p>}

                      <button
                        disabled={registerSubmitting}
                        onClick={submitRegistration}
                        className="rounded-lg bg-blue-600 px-4 py-2.5 font-semibold hover:bg-blue-700 disabled:bg-slate-700"
                      >
                        {registerSubmitting ? "Registering..." : "Register student"}
                      </button>
                    </div>
                  )}
                </article>

                <article className="mt-8 overflow-hidden rounded-2xl border border-slate-800 bg-slate-900">
                  <div className="p-6">
                    <h3 className="font-semibold">Registered students</h3>
                    <p className="mt-1 text-sm text-slate-400">
                      Remove a registration if a student was registered in error.
                    </p>
                  </div>

                  {regsState.status === "loading" && (
                    <div className="px-6 pb-6">
                      <LoadingState label="Loading registrations..." />
                    </div>
                  )}

                  {regsState.status === "error" && (
                    <div className="px-6 pb-6">
                      <ErrorState
                        message={regsState.message}
                        onRetry={() => selectedExamCode && loadRegistrations(selectedExamCode)}
                      />
                    </div>
                  )}

                  {regsState.status === "ready" && sortedRegistrations.length === 0 && (
                    <div className="px-6 pb-6">
                      <EmptyState message="No students registered for this examination yet." />
                    </div>
                  )}

                  {regsState.status === "ready" && sortedRegistrations.length > 0 && (
                    <div className="overflow-x-auto">
                      <table className="w-full min-w-[650px] text-left text-sm">
                        <thead className="border-y border-slate-800 bg-slate-800/70 text-slate-400">
                          <tr>
                            <th className="px-6 py-4">Student</th>
                            <th className="px-6 py-4">Registered</th>
                            <th className="px-6 py-4">Action</th>
                          </tr>
                        </thead>
                        <tbody>
                          {sortedRegistrations.map((registration) => {
                            const student = studentByPk.get(registration.student_id);
                            const isRemoving = removingId === registration.id;

                            return (
                              <tr key={registration.id} className="border-b border-slate-800 last:border-0">
                                <td className="px-6 py-4">
                                  <p className="font-medium">{student?.name ?? "Unknown student"}</p>
                                  <p className="text-xs text-slate-500">{student?.student_id ?? "—"}</p>
                                </td>
                                <td className="px-6 py-4 text-slate-400">
                                  {new Date(registration.created_at).toLocaleDateString("en-IN")}
                                </td>
                                <td className="px-6 py-4">
                                  <button
                                    disabled={isRemoving}
                                    onClick={() => removeRegistration(registration.id)}
                                    className="rounded-lg border border-slate-700 px-3 py-2 text-xs font-medium hover:bg-slate-800 disabled:opacity-50"
                                  >
                                    {isRemoving ? "Removing..." : "Remove"}
                                  </button>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}
                </article>
              </>
            )}
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
