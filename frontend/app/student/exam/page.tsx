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
import { listExamRegistrations, listExams } from "../../../lib/services";
import { ApiError } from "../../../lib/api";
import type { Exam } from "../../../lib/types";

type ExamRow = Exam & { registered: boolean };

type ExamsState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; exams: ExamRow[] };

export default function ExamPage() {
  const guard = useAuthGuard(["student"]);
  const user = guard.status === "ready" ? guard.user : null;
  const studentState = useOwnStudent(user);

  const [state, setState] = useState<ExamsState>({ status: "loading" });

  function load(code: string) {
    setState({ status: "loading" });
    listExams()
      .then(async (exams) => {
        // Small dataset (campus exam list), so checking registration
        // status per-exam client-side is reasonable — no bulk
        // "my registrations across all exams" endpoint exists.
        const rows = await Promise.all(
          exams.map(async (exam) => {
            const regs = await listExamRegistrations(exam.exam_code, { student_id: code }).catch(
              () => []
            );
            return { ...exam, registered: regs.length > 0 };
          })
        );
        setState({ status: "ready", exams: rows });
      })
      .catch((err) =>
        setState({
          status: "error",
          message: err instanceof ApiError ? err.message : "Failed to load examinations.",
        })
      );
  }

  useEffect(() => {
    if (studentState.status === "ready") {
      load(studentState.student.student_id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [studentState]);

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <PortalHeader portal="student" active="exam" />

      <section className="mx-auto max-w-7xl px-6 py-10">
        <h2 className="text-3xl font-bold">Examinations</h2>
        <p className="mt-2 text-slate-400">
          View upcoming examinations and your registration status.
        </p>

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
            {state.status === "loading" && <LoadingState label="Loading examinations..." />}

            {state.status === "error" && (
              <ErrorState
                message={state.message}
                onRetry={() => load(studentState.student.student_id)}
              />
            )}

            {state.status === "ready" && state.exams.length === 0 && (
              <EmptyState message="No examinations have been scheduled yet." />
            )}

            {state.status === "ready" && state.exams.length > 0 && (
              <div className="mt-8 grid gap-6 md:grid-cols-3">
                {state.exams.map((exam) => (
                  <div key={exam.id} className="rounded-xl border border-slate-800 bg-slate-900 p-6">
                    <h3 className="text-xl font-semibold">{exam.subject}</h3>

                    <div className="mt-5 space-y-3 text-sm">
                      <p>
                        <span className="text-slate-500">Code: </span>
                        {exam.exam_code}
                      </p>
                      <p>
                        <span className="text-slate-500">Scheduled: </span>
                        {new Date(exam.scheduled_at).toLocaleString()}
                      </p>
                      <p>
                        <span className="text-slate-500">Exam status: </span>
                        {exam.status}
                      </p>
                    </div>

                    <div className="mt-6 border-t border-slate-800 pt-4">
                      <span className={exam.registered ? "text-green-400" : "text-slate-500"}>
                        ● {exam.registered ? "Registered" : "Not registered"}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        <BackendDependencyNotice
          title="Self-service registration isn't available"
          detail="POST /examinations/{exam_code}/register is restricted to ADMIN/EXAM_OFFICER — a student account gets a 403 from the real backend. A 'Register' button here would have nothing real to call, so registration status is shown read-only; registering is handled by the Examination Office."
        />
      </section>
    </main>
  );
}
