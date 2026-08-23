"use client";

import { useEffect, useState } from "react";
import {
  PortalHeader,
  LoadingState,
  ErrorState,
  EmptyState,
} from "../../../components/portal-ui";
import { useAuthGuard } from "../../../lib/auth";
import { listStudents } from "../../../lib/services";
import { ApiError } from "../../../lib/api";
import type { StudentRead } from "../../../lib/types";

type State =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; students: StudentRead[] };

export default function FacultyStudentsPage() {
  const guard = useAuthGuard(["faculty"]);
  const [state, setState] = useState<State>({ status: "loading" });

  function load() {
    setState({ status: "loading" });
    listStudents()
      .then((students) => setState({ status: "ready", students }))
      .catch((err) =>
        setState({
          status: "error",
          message: err instanceof ApiError ? err.message : "Failed to load students.",
        })
      );
  }

  useEffect(() => {
    if (guard.status === "ready") load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [guard.status]);

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <PortalHeader portal="faculty" active="students" />

      <section className="mx-auto max-w-7xl px-6 py-10">
        <h2 className="text-3xl font-bold">Students</h2>
        <p className="mt-2 text-slate-400">
          Student directory, from the backend Student service.
        </p>

        {guard.status !== "ready" && <LoadingState label="Checking your session..." />}

        {guard.status === "ready" && state.status === "loading" && (
          <LoadingState label="Loading students..." />
        )}

        {guard.status === "ready" && state.status === "error" && (
          <ErrorState message={state.message} onRetry={load} />
        )}

        {guard.status === "ready" && state.status === "ready" && state.students.length === 0 && (
          <EmptyState message="No students found." />
        )}

        {guard.status === "ready" && state.status === "ready" && state.students.length > 0 && (
          <div className="mt-8 overflow-hidden rounded-xl border border-slate-800 bg-slate-900">
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead className="bg-slate-800">
                  <tr>
                    <th className="px-6 py-4">ID</th>
                    <th className="px-6 py-4">Name</th>
                    <th className="px-6 py-4">Email</th>
                    <th className="px-6 py-4">Department</th>
                    <th className="px-6 py-4">Course</th>
                    <th className="px-6 py-4">Enrollment Year</th>
                  </tr>
                </thead>

                <tbody>
                  {state.students.map((student) => (
                    <tr key={student.id} className="border-t border-slate-800 hover:bg-slate-800/50">
                      <td className="px-6 py-4 text-slate-400">{student.student_id}</td>
                      <td className="px-6 py-4 font-medium">{student.name}</td>
                      <td className="px-6 py-4 text-slate-400">{student.email}</td>
                      <td className="px-6 py-4">{student.department}</td>
                      <td className="px-6 py-4">{student.course}</td>
                      <td className="px-6 py-4">{student.enrollment_year}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </section>
    </main>
  );
}
