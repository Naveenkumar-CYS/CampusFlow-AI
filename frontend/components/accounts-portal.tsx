"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { LoadingState, ErrorState, EmptyState } from "./portal-ui";
import { useAuthGuard, logout } from "../lib/auth";
import { listFees, listStudents, payFee } from "../lib/services";
import { ApiError } from "../lib/api";
import type { Fee, FeeStatus, StudentRead } from "../lib/types";

// Same 4-tab layout as the rest of the staff portals (components/staff-portal.tsx)
// — this file only owns the "accounts" tab's content and data.
const NAV = [
  { key: "admin", label: "Admin", href: "/admin/dashboard" },
  { key: "accounts", label: "Accounts", href: "/accounts/dashboard" },
  { key: "warden", label: "Warden", href: "/warden/dashboard" },
  { key: "exam", label: "Examinations", href: "/exam/dashboard" },
];

type DataState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; fees: Fee[]; students: StudentRead[] };

export function AccountsPortal() {
  const router = useRouter();
  // ACCOUNTS owns fee collection; ADMIN also has staff access to the same
  // /fees endpoints per backend RBAC (app/api/fees.py _STAFF), so both are
  // allowed in here — same pattern as the rest of the login->portal map.
  const guard = useAuthGuard(["accounts", "admin"]);

  const [state, setState] = useState<DataState>({ status: "loading" });
  const [payingFeeId, setPayingFeeId] = useState<string | null>(null);
  const [payReference, setPayReference] = useState("");
  const [payError, setPayError] = useState<string | null>(null);
  const [paySubmitting, setPaySubmitting] = useState(false);

  function load() {
    setState({ status: "loading" });
    Promise.all([listFees(), listStudents()])
      .then(([fees, students]) => setState({ status: "ready", fees, students }))
      .catch((err) =>
        setState({
          status: "error",
          message: err instanceof ApiError ? err.message : "Failed to load fee records.",
        })
      );
  }

  useEffect(() => {
    if (guard.status === "ready") load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [guard.status]);

  const fees = state.status === "ready" ? state.fees : [];
  const students = state.status === "ready" ? state.students : [];
  const studentByPk = new Map(students.map((s) => [s.id, s]));

  const collectedAmount = fees
    .filter((f) => f.status === "PAID")
    .reduce((sum, f) => sum + Number(f.amount), 0);
  const outstandingAmount = fees
    .filter((f) => f.status === "PENDING" || f.status === "OVERDUE")
    .reduce((sum, f) => sum + Number(f.amount), 0);
  const outstandingCount = fees.filter((f) => f.status === "PENDING" || f.status === "OVERDUE").length;
  const paidCount = fees.filter((f) => f.status === "PAID").length;

  const sortedFees = fees
    .slice()
    .sort((a, b) => (a.due_date < b.due_date ? 1 : -1));

  function startPayment(feeId: string) {
    setPayingFeeId(feeId);
    setPayReference("");
    setPayError(null);
  }

  async function submitPayment(feeId: string) {
    if (!payReference.trim()) {
      setPayError("Enter a payment reference.");
      return;
    }
    setPaySubmitting(true);
    setPayError(null);
    try {
      await payFee(feeId, { payment_reference: payReference.trim() });
      setPayingFeeId(null);
      setPayReference("");
      load();
    } catch (err) {
      setPayError(err instanceof ApiError ? err.message : "Failed to record payment.");
    } finally {
      setPaySubmitting(false);
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
            <p className="text-sm text-slate-400">Accounts Portal</p>
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
                item.key === "accounts"
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
        <p className="text-slate-400">Finance operations</p>
        <h2 className="mt-1 text-3xl font-bold">Fee Collection</h2>

        {guard.status !== "ready" && <LoadingState label="Checking your session..." />}

        {guard.status === "ready" && state.status === "loading" && (
          <LoadingState label="Loading fee records..." />
        )}

        {guard.status === "ready" && state.status === "error" && (
          <ErrorState message={state.message} onRetry={load} />
        )}

        {guard.status === "ready" && state.status === "ready" && (
          <>
            <div className="mt-8 grid gap-5 sm:grid-cols-3">
              <Card
                label="Collected"
                value={`₹${collectedAmount.toLocaleString("en-IN")}`}
                note={`${paidCount} payment${paidCount === 1 ? "" : "s"} recorded`}
                color="text-emerald-400"
              />
              <Card
                label="Outstanding dues"
                value={`₹${outstandingAmount.toLocaleString("en-IN")}`}
                note={`${outstandingCount} fee record${outstandingCount === 1 ? "" : "s"} need follow-up`}
                color="text-amber-300"
              />
              <Card label="Total fee records" value={String(fees.length)} note="Across all students" />
            </div>

            <article className="mt-8 overflow-hidden rounded-2xl border border-slate-800 bg-slate-900">
              <div className="p-6">
                <h3 className="font-semibold">Fee records</h3>
                <p className="mt-1 text-sm text-slate-400">
                  Record a payment to mark a fee PAID and generate the payment reference.
                </p>
              </div>

              {sortedFees.length === 0 ? (
                <div className="px-6 pb-6">
                  <EmptyState message="No fee records yet." />
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[750px] text-left text-sm">
                    <thead className="border-y border-slate-800 bg-slate-800/70 text-slate-400">
                      <tr>
                        <th className="px-6 py-4">Student</th>
                        <th className="px-6 py-4">Fee Type</th>
                        <th className="px-6 py-4">Amount</th>
                        <th className="px-6 py-4">Due Date</th>
                        <th className="px-6 py-4">Status</th>
                        <th className="px-6 py-4">Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sortedFees.map((fee) => {
                        const student = studentByPk.get(fee.student_id);
                        const canPay = fee.status === "PENDING" || fee.status === "OVERDUE";
                        const isPayingThis = payingFeeId === fee.fee_id;

                        return (
                          <tr key={fee.id} className="border-b border-slate-800 last:border-0">
                            <td className="px-6 py-4">
                              <p className="font-medium">{student?.name ?? "Unknown student"}</p>
                              <p className="text-xs text-slate-500">
                                {student?.student_id ?? fee.student_id}
                              </p>
                            </td>
                            <td className="px-6 py-4">{fee.fee_type}</td>
                            <td className="px-6 py-4">₹{Number(fee.amount).toLocaleString("en-IN")}</td>
                            <td className="px-6 py-4 text-slate-400">{fee.due_date}</td>
                            <td className="px-6 py-4">
                              <StatusBadge status={fee.status} />
                            </td>
                            <td className="px-6 py-4">
                              {!canPay && (
                                <span className="text-xs text-slate-500">
                                  {fee.payment_reference ?? "—"}
                                </span>
                              )}

                              {canPay && !isPayingThis && (
                                <button
                                  onClick={() => startPayment(fee.fee_id)}
                                  className="rounded-lg bg-blue-600 px-3 py-2 font-medium hover:bg-blue-700"
                                >
                                  Record payment
                                </button>
                              )}

                              {canPay && isPayingThis && (
                                <div className="flex flex-col gap-2">
                                  <input
                                    type="text"
                                    autoFocus
                                    value={payReference}
                                    onChange={(e) => setPayReference(e.target.value)}
                                    placeholder="Payment reference"
                                    className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white placeholder:text-slate-500"
                                  />
                                  {payError && (
                                    <p className="text-xs text-red-400">{payError}</p>
                                  )}
                                  <div className="flex gap-2">
                                    <button
                                      disabled={paySubmitting}
                                      onClick={() => submitPayment(fee.fee_id)}
                                      className="rounded-lg bg-blue-600 px-3 py-2 text-xs font-medium hover:bg-blue-700 disabled:bg-slate-700"
                                    >
                                      {paySubmitting ? "Saving..." : "Confirm"}
                                    </button>
                                    <button
                                      disabled={paySubmitting}
                                      onClick={() => {
                                        setPayingFeeId(null);
                                        setPayError(null);
                                      }}
                                      className="rounded-lg border border-slate-700 px-3 py-2 text-xs font-medium hover:bg-slate-800"
                                    >
                                      Cancel
                                    </button>
                                  </div>
                                </div>
                              )}
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

function StatusBadge({ status }: { status: FeeStatus }) {
  const colors: Record<FeeStatus, string> = {
    PAID: "bg-emerald-500/15 text-emerald-300 ring-emerald-400/30",
    PENDING: "bg-amber-500/15 text-amber-300 ring-amber-400/30",
    OVERDUE: "bg-red-500/15 text-red-300 ring-red-400/30",
    CANCELLED: "bg-slate-500/15 text-slate-400 ring-slate-400/30",
  };
  return (
    <span className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ring-1 ${colors[status]}`}>
      {status}
    </span>
  );
}
