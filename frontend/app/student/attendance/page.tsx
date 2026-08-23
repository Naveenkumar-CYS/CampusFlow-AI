"use client";

import { useEffect, useState } from "react";
import {
  PortalHeader,
  LoadingState,
  ErrorState,
  EmptyState,
  BackendDependencyNotice,
} from "../../../components/portal-ui";
import { useAuthGuard } from "../../../lib/auth";
import { useOwnStudent } from "../../../lib/own-student";
import { listAttendance } from "../../../lib/services";
import { ApiError } from "../../../lib/api";
import type { AttendanceRecord } from "../../../lib/types";

type RecordsState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; records: AttendanceRecord[] };

export default function AttendancePage() {
  const guard = useAuthGuard(["student"]);
  const user = guard.status === "ready" ? guard.user : null;
  const studentState = useOwnStudent(user);

  const [state, setState] = useState<RecordsState>({ status: "loading" });

  function load(code: string) {
    setState({ status: "loading" });
    listAttendance({ student_id: code })
      .then((records) => setState({ status: "ready", records }))
      .catch((err) =>
        setState({
          status: "error",
          message: err instanceof ApiError ? err.message : "Failed to load attendance.",
        })
      );
  }

  useEffect(() => {
    if (studentState.status === "ready") {
      load(studentState.student.student_id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [studentState]);

  const bySubject: [string, AttendanceRecord[]][] =
    state.status === "ready" ? groupBySubject(state.records) : [];

  const overallPct =
    state.status === "ready" && state.records.length
      ? Math.round(
          (state.records.filter((r) => r.status === "PRESENT" || r.status === "LATE").length /
            state.records.length) *
            100
        )
      : null;

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <PortalHeader portal="student" active="attendance" />

      <section className="mx-auto max-w-7xl px-6 py-10">
        <h2 className="text-3xl font-bold">Attendance</h2>
        <p className="mt-2 text-slate-400">View your current subject-wise attendance.</p>

        {guard.status !== "ready" && <LoadingState label="Checking your session..." />}

        {guard.status === "ready" && studentState.status === "loading" && (
          <LoadingState label="Loading your profile..." />
        )}

        {guard.status === "ready" && studentState.status === "error" && (
          <ErrorState message={studentState.message} />
        )}

        {guard.status === "ready" && studentState.status === "unresolvable" && (
          <BackendDependencyNotice
            title="Your account isn't linked to a student record yet"
            detail="No Student record is linked to this login account (GET /students/me returned no match). Contact an administrator to have your account linked to your student record."
          />
        )}

        {guard.status === "ready" && studentState.status === "ready" && (
          <>
            {state.status === "loading" && <LoadingState label="Loading attendance records..." />}

            {state.status === "error" && (
              <ErrorState
                message={state.message}
                onRetry={() => load(studentState.student.student_id)}
              />
            )}

            {state.status === "ready" && state.records.length === 0 && (
              <EmptyState message="No attendance records yet." />
            )}

            {state.status === "ready" && state.records.length > 0 && (
              <div className="mt-8 rounded-xl border border-slate-800 bg-slate-900 p-6">
                <div className="mb-6">
                  <p className="text-sm text-slate-400">Overall Attendance</p>
                  <p className="mt-1 text-4xl font-bold text-blue-500">
                    {overallPct !== null ? `${overallPct}%` : "—"}
                  </p>
                </div>

                <div className="space-y-6">
                  {bySubject.map(([subject, records]) => {
                    const attended = records.filter(
                      (r) => r.status === "PRESENT" || r.status === "LATE"
                    ).length;
                    const total = records.length;
                    const percentage = Math.round((attended / total) * 100);

                    return (
                      <div key={subject}>
                        <div className="flex justify-between">
                          <span>{subject}</span>
                          <span className="text-slate-400">
                            {attended}/{total} ({percentage}%)
                          </span>
                        </div>

                        <div className="mt-2 h-2 rounded-full bg-slate-800">
                          <div
                            className="h-2 rounded-full bg-blue-500"
                            style={{ width: `${percentage}%` }}
                          />
                        </div>

                        <ul className="mt-3 space-y-1 text-xs text-slate-500">
                          {records
                            .slice()
                            .sort((a, b) => (a.session_date < b.session_date ? 1 : -1))
                            .slice(0, 5)
                            .map((r) => (
                              <li key={r.id} className="flex justify-between">
                                <span>{r.session_date}</span>
                                <StatusBadge status={r.status} />
                              </li>
                            ))}
                        </ul>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </>
        )}
      </section>
    </main>
  );
}

function groupBySubject(records: AttendanceRecord[]): [string, AttendanceRecord[]][] {
  const grouped: Record<string, AttendanceRecord[]> = {};
  for (const record of records) {
    if (!grouped[record.subject]) grouped[record.subject] = [];
    grouped[record.subject].push(record);
  }
  return Object.entries(grouped);
}

function StatusBadge({ status }: { status: AttendanceRecord["status"] }) {
  const colors: Record<AttendanceRecord["status"], string> = {
    PRESENT: "text-green-400",
    LATE: "text-amber-400",
    EXCUSED: "text-blue-400",
    ABSENT: "text-red-400",
  };
  return <span className={colors[status]}>{status}</span>;
}
