"use client";

import { useEffect, useState } from "react";
import { PortalHeader, LoadingState, ErrorState, BackendDependencyNotice } from "../../../components/portal-ui";
import { useAuthGuard } from "../../../lib/auth";
import { useOwnStudent } from "../../../lib/own-student";
import { listAttendance, listExams, listHostelAllocations, listOwnFees } from "../../../lib/services";
import { ApiError } from "../../../lib/api";
import type { Allocation } from "../../../lib/types";

type Summary =
  | { status: "loading" }
  | { status: "error"; message: string }
  | {
      status: "ready";
      attendancePct: number | null;
      hostel: Allocation | null;
      upcomingExamCount: number;
      feesCount: number;
      feesOutstanding: number;
    };

export default function StudentDashboard() {
  const guard = useAuthGuard(["student"]);
  const user = guard.status === "ready" ? guard.user : null;
  const studentState = useOwnStudent(user);

  const [summary, setSummary] = useState<Summary>({ status: "loading" });

  useEffect(() => {
    if (studentState.status !== "ready") return;
    let cancelled = false;
    setSummary({ status: "loading" });

    const code = studentState.student.student_id;

    (async () => {
      try {
        const [attendance, allocations, exams, fees] = await Promise.all([
          listAttendance({ student_id: code }),
          listHostelAllocations({ student_id: code }),
          listExams(),
          listOwnFees(),
        ]);

        const attendancePct = attendance.length
          ? Math.round(
              (attendance.filter((r) => r.status === "PRESENT" || r.status === "LATE").length /
                attendance.length) *
                100
            )
          : null;

        const hostel = allocations.find((a) => a.status === "ACTIVE") ?? null;
        const upcomingExamCount = exams.filter((e) => e.status === "SCHEDULED").length;

        const feesOutstanding = fees
          .filter((f) => f.status === "PENDING" || f.status === "OVERDUE")
          .reduce((sum, f) => sum + Number(f.amount), 0);

        if (!cancelled) {
          setSummary({
            status: "ready",
            attendancePct,
            hostel,
            upcomingExamCount,
            feesCount: fees.length,
            feesOutstanding,
          });
        }
      } catch (err) {
        if (!cancelled) {
          setSummary({
            status: "error",
            message: err instanceof ApiError ? err.message : "Failed to load dashboard data.",
          });
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [studentState]);

  if (guard.status !== "ready") {
    return (
      <main className="min-h-screen bg-slate-950 text-white">
        <div className="mx-auto max-w-7xl px-6 py-10">
          <LoadingState label="Checking your session..." />
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <PortalHeader portal="student" active="dashboard" />

      <section className="mx-auto max-w-7xl px-6 py-10">
        <h2 className="text-3xl font-bold">Student Dashboard</h2>
        <p className="mt-2 text-slate-400">
          Welcome, {studentState.status === "ready" ? studentState.student.name : guard.user.email}
        </p>

        {studentState.status === "loading" && <LoadingState label="Loading your profile..." />}

        {studentState.status === "error" && <ErrorState message={studentState.message} />}

        {studentState.status === "unresolvable" && (
          <BackendDependencyNotice
            title="Your account isn't linked to a student record yet"
            detail="No Student record is linked to this login account (GET /students/me returned no match). Contact an administrator to have your account linked to your student record."
          />
        )}

        {studentState.status === "ready" && (
          <>
            <div className="mt-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
              <DashboardCard
                title="Attendance"
                value={
                  summary.status === "ready"
                    ? summary.attendancePct !== null
                      ? `${summary.attendancePct}%`
                      : "No records yet"
                    : summary.status === "error"
                      ? "—"
                      : "…"
                }
              />

              <DashboardCard
                title="Fees"
                value={
                  summary.status === "ready"
                    ? summary.feesCount === 0
                      ? "No fee records"
                      : summary.feesOutstanding > 0
                        ? `${summary.feesOutstanding.toFixed(2)} due`
                        : "All paid"
                    : summary.status === "error"
                      ? "—"
                      : "…"
                }
              />

              <DashboardCard
                title="Hostel"
                value={
                  summary.status === "ready"
                    ? summary.hostel
                      ? "Allocated"
                      : "Not allocated"
                    : summary.status === "error"
                      ? "—"
                      : "…"
                }
              />

              <DashboardCard
                title="Exams"
                value={
                  summary.status === "ready"
                    ? `${summary.upcomingExamCount} upcoming`
                    : summary.status === "error"
                      ? "—"
                      : "…"
                }
              />
            </div>

            {summary.status === "error" && <ErrorState message={summary.message} />}
          </>
        )}
      </section>
    </main>
  );
}

function DashboardCard({ title, value }: { title: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-6 shadow">
      <p className="text-slate-400">{title}</p>
      <h2 className="mt-2 text-2xl font-bold">{value}</h2>
    </div>
  );
}
