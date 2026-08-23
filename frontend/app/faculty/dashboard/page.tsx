"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { PortalHeader, LoadingState, ErrorState } from "../../../components/portal-ui";
import { useAuthGuard } from "../../../lib/auth";
import { listAttendance, listStudents } from "../../../lib/services";
import { ApiError } from "../../../lib/api";

type Summary =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; studentCount: number; todayMarked: number; todayPresentPct: number | null };

export default function FacultyDashboard() {
  const guard = useAuthGuard(["faculty"]);
  const [summary, setSummary] = useState<Summary>({ status: "loading" });

  useEffect(() => {
    if (guard.status !== "ready") return;
    let cancelled = false;

    (async () => {
      try {
        const [students, attendance] = await Promise.all([listStudents(), listAttendance()]);
        const today = new Date().toISOString().slice(0, 10);
        const todayRecords = attendance.filter((r) => r.session_date === today);
        const present = todayRecords.filter((r) => r.status === "PRESENT" || r.status === "LATE").length;

        if (!cancelled) {
          setSummary({
            status: "ready",
            studentCount: students.length,
            todayMarked: todayRecords.length,
            todayPresentPct: todayRecords.length ? Math.round((present / todayRecords.length) * 100) : null,
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
  }, [guard.status]);

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
      <PortalHeader portal="faculty" active="dashboard" />

      <section className="mx-auto max-w-7xl px-6 py-10">
        <p className="text-slate-400">Welcome back,</p>
        <h2 className="mt-1 text-3xl font-bold">{guard.user.email}</h2>

        {summary.status === "loading" && <LoadingState label="Loading dashboard data..." />}
        {summary.status === "error" && <ErrorState message={summary.message} />}

        {summary.status === "ready" && (
          <div className="mt-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard title="Students" value={String(summary.studentCount)} description="Total students in the system" />
            <StatCard
              title="Today's Attendance"
              value={summary.todayPresentPct !== null ? `${summary.todayPresentPct}%` : "Not marked yet"}
              description={`${summary.todayMarked} record(s) marked today`}
            />
            <NavCard title="Students" description="Browse the student directory" href="/faculty/students" />
            <NavCard title="Mark Attendance" description="Record today's attendance" href="/faculty/attendance" />
          </div>
        )}
      </section>
    </main>
  );
}

function StatCard({ title, value, description }: { title: string; value: string; description: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-6">
      <p className="text-slate-400">{title}</p>
      <p className="mt-3 text-3xl font-bold text-blue-500">{value}</p>
      <p className="mt-2 text-sm text-slate-500">{description}</p>
    </div>
  );
}

function NavCard({ title, description, href }: { title: string; description: string; href: string }) {
  return (
    <Link
      href={href}
      className="rounded-xl border border-slate-800 bg-slate-900 p-6 transition hover:-translate-y-1 hover:border-blue-500"
    >
      <p className="text-slate-400">{title}</p>
      <p className="mt-2 text-sm text-slate-500">{description}</p>
    </Link>
  );
}
