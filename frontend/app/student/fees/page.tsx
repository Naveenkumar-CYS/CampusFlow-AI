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
import { listOwnFees } from "../../../lib/services";
import { ApiError } from "../../../lib/api";
import type { Fee } from "../../../lib/types";

type FeesState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; fees: Fee[] };

export default function FeesPage() {
  const guard = useAuthGuard(["student"]);
  const user = guard.status === "ready" ? guard.user : null;
  const studentState = useOwnStudent(user);

  const [state, setState] = useState<FeesState>({ status: "loading" });

  function load() {
    setState({ status: "loading" });
    listOwnFees()
      .then((fees) => setState({ status: "ready", fees }))
      .catch((err) =>
        setState({
          status: "error",
          message: err instanceof ApiError ? err.message : "Failed to load fees.",
        })
      );
  }

  useEffect(() => {
    if (studentState.status === "ready") {
      load();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [studentState]);

  const sortedFees =
    state.status === "ready"
      ? state.fees.slice().sort((a, b) => (a.due_date < b.due_date ? 1 : -1))
      : [];

  const totalPending =
    state.status === "ready"
      ? state.fees
          .filter((f) => f.status === "PENDING" || f.status === "OVERDUE")
          .reduce((sum, f) => sum + Number(f.amount), 0)
      : 0;

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <PortalHeader portal="student" active="fees" />

      <section className="mx-auto max-w-7xl px-6 py-10">
        <h2 className="text-3xl font-bold">Fees</h2>
        <p className="mt-2 text-slate-400">View your fee status and payment history.</p>

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
            {state.status === "loading" && <LoadingState label="Loading fees..." />}

            {state.status === "error" && <ErrorState message={state.message} onRetry={load} />}

            {state.status === "ready" && state.fees.length === 0 && (
              <EmptyState message="No fee records yet." />
            )}

            {state.status === "ready" && state.fees.length > 0 && (
              <>
                <div className="mt-8 rounded-xl border border-slate-800 bg-slate-900 p-6">
                  <p className="text-sm text-slate-400">Outstanding Balance</p>
                  <p className="mt-1 text-4xl font-bold text-blue-500">
                    {totalPending.toFixed(2)}
                  </p>
                </div>

                <div className="mt-8 overflow-x-auto rounded-xl border border-slate-800 bg-slate-900">
                  <table className="w-full text-left text-sm">
                    <thead className="border-b border-slate-800 text-slate-400">
                      <tr>
                        <th className="px-6 py-4 font-medium">Fee Type</th>
                        <th className="px-6 py-4 font-medium">Amount</th>
                        <th className="px-6 py-4 font-medium">Due Date</th>
                        <th className="px-6 py-4 font-medium">Status</th>
                        <th className="px-6 py-4 font-medium">Payment Reference</th>
                        <th className="px-6 py-4 font-medium">Paid Date</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sortedFees.map((fee) => (
                        <tr key={fee.id} className="border-b border-slate-800 last:border-0">
                          <td className="px-6 py-4">{fee.fee_type}</td>
                          <td className="px-6 py-4">{Number(fee.amount).toFixed(2)}</td>
                          <td className="px-6 py-4 text-slate-400">{fee.due_date}</td>
                          <td className="px-6 py-4">
                            <StatusBadge status={fee.status} />
                          </td>
                          <td className="px-6 py-4 text-slate-400">
                            {fee.payment_reference ?? "—"}
                          </td>
                          <td className="px-6 py-4 text-slate-400">
                            {fee.paid_at ? new Date(fee.paid_at).toLocaleDateString() : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </>
        )}
      </section>
    </main>
  );
}

function StatusBadge({ status }: { status: Fee["status"] }) {
  const colors: Record<Fee["status"], string> = {
    PAID: "text-green-400",
    PENDING: "text-amber-400",
    OVERDUE: "text-red-400",
    CANCELLED: "text-slate-500",
  };
  return <span className={colors[status]}>{status}</span>;
}
