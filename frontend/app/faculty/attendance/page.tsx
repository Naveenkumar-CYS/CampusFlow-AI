"use client";

import { useEffect, useState } from "react";
import {
  PortalHeader,
  LoadingState,
  ErrorState,
  EmptyState,
} from "../../../components/portal-ui";
import { useAuthGuard } from "../../../lib/auth";
import { createAttendanceRecord, listAttendance, listStudents } from "../../../lib/services";
import { ApiError } from "../../../lib/api";
import type { AttendanceRecord, AttendanceStatus, StudentRead } from "../../../lib/types";

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

type StudentsState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; students: StudentRead[] };

type RecordsState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; records: AttendanceRecord[] };

export default function FacultyAttendancePage() {
  const guard = useAuthGuard(["faculty"]);
  const user = guard.status === "ready" ? guard.user : null;

  const [studentsState, setStudentsState] = useState<StudentsState>({ status: "loading" });
  const [recordsState, setRecordsState] = useState<RecordsState>({ status: "loading" });

  const [studentCode, setStudentCode] = useState("");
  const [subject, setSubject] = useState("");
  const [sessionDate, setSessionDate] = useState(todayIso());
  const [attendanceStatus, setAttendanceStatus] = useState<AttendanceStatus>("PRESENT");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitSuccess, setSubmitSuccess] = useState<string | null>(null);

  function loadStudents() {
    setStudentsState({ status: "loading" });
    listStudents()
      .then((students) => {
        setStudentsState({ status: "ready", students });
        if (students.length && !studentCode) setStudentCode(students[0].student_id);
      })
      .catch((err) =>
        setStudentsState({
          status: "error",
          message: err instanceof ApiError ? err.message : "Failed to load students.",
        })
      );
  }

  function loadRecordsForDate(date: string) {
    setRecordsState({ status: "loading" });
    listAttendance()
      .then((records) =>
        setRecordsState({
          status: "ready",
          records: records.filter((r) => r.session_date === date),
        })
      )
      .catch((err) =>
        setRecordsState({
          status: "error",
          message: err instanceof ApiError ? err.message : "Failed to load attendance records.",
        })
      );
  }

  useEffect(() => {
    if (guard.status === "ready") {
      loadStudents();
      loadRecordsForDate(sessionDate);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [guard.status]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!studentCode || !subject.trim()) {
      setSubmitError("Select a student and enter a subject.");
      return;
    }

    setSubmitting(true);
    setSubmitError(null);
    setSubmitSuccess(null);

    try {
      await createAttendanceRecord({
        student_id: studentCode,
        subject: subject.trim(),
        session_date: sessionDate,
        status: attendanceStatus,
        marked_by: user?.email,
      });
      setSubmitSuccess("Attendance recorded.");
      loadRecordsForDate(sessionDate);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setSubmitError(
          "An attendance record already exists for this student/subject/date. Editing existing records isn't wired up in this session — pick a different subject or date."
        );
      } else if (err instanceof ApiError && err.status === 404) {
        setSubmitError("That student ID wasn't found on the backend.");
      } else if (err instanceof ApiError) {
        setSubmitError(err.message);
      } else {
        setSubmitError("Something went wrong recording attendance.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  const records = recordsState.status === "ready" ? recordsState.records : [];
  const presentCount = records.filter((r) => r.status === "PRESENT" || r.status === "LATE").length;

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <PortalHeader portal="faculty" active="attendance" />

      <section className="mx-auto max-w-7xl px-6 py-10">
        <h2 className="text-3xl font-bold">Mark Attendance</h2>
        <p className="mt-2 text-slate-400">Record attendance for a student and subject.</p>

        {guard.status !== "ready" && <LoadingState label="Checking your session..." />}

        {guard.status === "ready" && studentsState.status === "error" && (
          <ErrorState message={studentsState.message} onRetry={loadStudents} />
        )}

        {guard.status === "ready" && studentsState.status !== "error" && (
          <form
            onSubmit={handleSubmit}
            className="mt-8 grid gap-4 rounded-xl border border-slate-800 bg-slate-900 p-6 sm:grid-cols-2 lg:grid-cols-4"
          >
            <div className="sm:col-span-2 lg:col-span-1">
              <label className="mb-1 block text-sm text-slate-400">Student</label>
              <select
                value={studentCode}
                onChange={(e) => setStudentCode(e.target.value)}
                disabled={studentsState.status !== "ready"}
                className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2"
              >
                {studentsState.status === "loading" && <option>Loading...</option>}
                {studentsState.status === "ready" &&
                  studentsState.students.map((s) => (
                    <option key={s.id} value={s.student_id}>
                      {s.student_id} — {s.name}
                    </option>
                  ))}
              </select>
            </div>

            <div>
              <label className="mb-1 block text-sm text-slate-400">Subject</label>
              <input
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                placeholder="e.g. Data Structures"
                className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2"
              />
            </div>

            <div>
              <label className="mb-1 block text-sm text-slate-400">Session Date</label>
              <input
                type="date"
                value={sessionDate}
                onChange={(e) => {
                  setSessionDate(e.target.value);
                  loadRecordsForDate(e.target.value);
                }}
                className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2"
              />
            </div>

            <div>
              <label className="mb-1 block text-sm text-slate-400">Status</label>
              <select
                value={attendanceStatus}
                onChange={(e) => setAttendanceStatus(e.target.value as AttendanceStatus)}
                className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2"
              >
                <option value="PRESENT">Present</option>
                <option value="ABSENT">Absent</option>
                <option value="LATE">Late</option>
                <option value="EXCUSED">Excused</option>
              </select>
            </div>

            <div className="sm:col-span-2 lg:col-span-4">
              <button
                type="submit"
                disabled={submitting || studentsState.status !== "ready"}
                className="rounded-lg bg-blue-600 px-6 py-3 font-semibold hover:bg-blue-700 disabled:opacity-50"
              >
                {submitting ? "Saving..." : "Save Attendance"}
              </button>

              {submitError && <p className="mt-3 text-sm text-red-400">{submitError}</p>}
              {submitSuccess && <p className="mt-3 text-sm text-green-400">{submitSuccess}</p>}
            </div>
          </form>
        )}

        {guard.status === "ready" && (
          <>
            <h3 className="mt-10 text-xl font-semibold">Records for {sessionDate}</h3>

            {recordsState.status === "loading" && <LoadingState label="Loading records..." />}

            {recordsState.status === "error" && (
              <ErrorState message={recordsState.message} onRetry={() => loadRecordsForDate(sessionDate)} />
            )}

            {recordsState.status === "ready" && records.length === 0 && (
              <EmptyState message="No attendance recorded for this date yet." />
            )}

            {recordsState.status === "ready" && records.length > 0 && (
              <>
                <div className="mt-4 grid gap-4 sm:grid-cols-3">
                  <StatCard label="Total Records" value={String(records.length)} />
                  <StatCard label="Present/Late" value={String(presentCount)} color="text-green-400" />
                  <StatCard label="Absent" value={String(records.length - presentCount)} color="text-red-400" />
                </div>

                <div className="mt-6 overflow-hidden rounded-xl border border-slate-800 bg-slate-900">
                  <div className="overflow-x-auto">
                    <table className="w-full text-left">
                      <thead className="bg-slate-800">
                        <tr>
                          <th className="px-6 py-4">Subject</th>
                          <th className="px-6 py-4">Status</th>
                          <th className="px-6 py-4">Marked By</th>
                        </tr>
                      </thead>
                      <tbody>
                        {records.map((r) => (
                          <tr key={r.id} className="border-t border-slate-800">
                            <td className="px-6 py-4 font-medium">{r.subject}</td>
                            <td className="px-6 py-4">
                              <StatusBadge status={r.status} />
                            </td>
                            <td className="px-6 py-4 text-slate-400">{r.marked_by ?? "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </>
            )}
          </>
        )}
      </section>
    </main>
  );
}

function StatCard({ label, value, color = "text-white" }: { label: string; value: string; color?: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
      <p className="text-sm text-slate-400">{label}</p>
      <p className={`mt-2 text-3xl font-bold ${color}`}>{value}</p>
    </div>
  );
}

function StatusBadge({ status }: { status: AttendanceStatus }) {
  const colors: Record<AttendanceStatus, string> = {
    PRESENT: "text-green-400",
    LATE: "text-amber-400",
    EXCUSED: "text-blue-400",
    ABSENT: "text-red-400",
  };
  return <span className={colors[status]}>{status}</span>;
}
