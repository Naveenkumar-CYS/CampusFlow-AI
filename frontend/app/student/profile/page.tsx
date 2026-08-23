"use client";

import { PortalHeader, LoadingState, ErrorState, BackendDependencyNotice } from "../../../components/portal-ui";
import { useAuthGuard } from "../../../lib/auth";
import { useOwnStudent } from "../../../lib/own-student";

export default function ProfilePage() {
  const guard = useAuthGuard(["student"]);
  const user = guard.status === "ready" ? guard.user : null;
  const studentState = useOwnStudent(user);

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <PortalHeader portal="student" active="profile" />

      <section className="mx-auto max-w-7xl px-6 py-10">
        <h2 className="text-3xl font-bold">Profile</h2>
        <p className="mt-2 text-slate-400">Your student record on file.</p>

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
          <div className="mt-8 grid gap-6 md:grid-cols-2">
            <div className="rounded-xl border border-slate-800 bg-slate-900 p-6">
              <h3 className="text-xl font-semibold">Identity</h3>
              <dl className="mt-4 space-y-4">
                <Field label="Student ID" value={studentState.student.student_id} />
                <Field label="Name" value={studentState.student.name} />
                <Field label="Email" value={studentState.student.email} />
                <Field
                  label="Phone"
                  value={studentState.student.phone ?? "Not on file"}
                />
              </dl>
            </div>

            <div className="rounded-xl border border-slate-800 bg-slate-900 p-6">
              <h3 className="text-xl font-semibold">Academics</h3>
              <dl className="mt-4 space-y-4">
                <Field label="Department" value={studentState.student.department} />
                <Field label="Course" value={studentState.student.course} />
                <Field
                  label="Enrollment Year"
                  value={String(studentState.student.enrollment_year)}
                />
              </dl>
            </div>
          </div>
        )}
      </section>
    </main>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-sm text-slate-400">{label}</dt>
      <dd className="mt-1 text-lg font-medium">{value}</dd>
    </div>
  );
}
