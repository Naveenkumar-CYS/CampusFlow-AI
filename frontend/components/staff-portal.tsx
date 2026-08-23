"use client";

import Link from "next/link";
import { useState, type ReactNode } from "react";

type Portal = "admin" | "accounts" | "warden" | "exam";

const navigation: { key: Portal; label: string; href: string }[] = [
  { key: "admin", label: "Admin", href: "/admin/dashboard" },
  { key: "accounts", label: "Accounts", href: "/accounts/dashboard" },
  { key: "warden", label: "Warden", href: "/warden/dashboard" },
  { key: "exam", label: "Examinations", href: "/exam/dashboard" },
];

export function StaffPortal({ portal }: { portal: Portal }) {
  const [paymentReceived, setPaymentReceived] = useState(false);
  const [roomAllocated, setRoomAllocated] = useState(false);
  const [examApproved, setExamApproved] = useState(false);
  const [advisoryAcknowledged, setAdvisoryAcknowledged] = useState(false);

  const title =
    navigation.find((item) => item.key === portal)?.label ?? "Staff";

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-slate-800">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-5">
          <div>
            <h1 className="text-2xl font-bold">
              Campus<span className="text-blue-500">Flow</span> AI
            </h1>
            <p className="text-sm text-slate-400">{title} Portal</p>
          </div>

          <Link
            href="/login"
            className="rounded-lg border border-slate-700 px-4 py-2 text-sm hover:bg-slate-800"
          >
            Logout
          </Link>
        </div>
      </header>

      <nav className="border-b border-slate-800 bg-slate-900/50">
        <div className="mx-auto flex max-w-7xl gap-2 overflow-x-auto px-6 py-3">
          {navigation.map((item) => (
            <Link
              key={item.key}
              href={item.href}
              className={`whitespace-nowrap rounded-lg px-4 py-2 text-sm font-medium ${
                item.key === portal
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
        {portal === "admin" && (
          <>
            <p className="text-slate-400">Institutional overview</p>
            <h2 className="mt-1 text-3xl font-bold">Campus Command Center</h2>

            <div className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
              <Card label="Active Students" value="2,486" note="Across 8 departments" />
              <Card label="Fee Collection" value="₹18.4L" note="84% collected this term" color="text-emerald-400" />
              <Card label="Hostel Occupancy" value="92%" note="736 of 800 beds assigned" color="text-amber-300" />
              <Card label="Exam Eligibility" value="96%" note="Students cleared to register" color="text-violet-300" />
            </div>

            <div className="mt-8 grid gap-6 lg:grid-cols-3">
              <article className="rounded-2xl border border-blue-500/30 bg-blue-500/10 p-6 lg:col-span-2">
                <Badge>AI advisory — human review required</Badge>
                <h3 className="mt-4 text-xl font-semibold">
                  Attendance risk detected
                </h3>
                <p className="mt-2 leading-7 text-slate-300">
                  12 students have attendance below 75%. CampusFlow creates
                  an advisory for faculty review; no student is penalised
                  automatically.
                </p>

                <button
                  onClick={() => setAdvisoryAcknowledged(true)}
                  className="mt-5 rounded-lg bg-blue-600 px-4 py-2.5 font-semibold hover:bg-blue-700"
                >
                  {advisoryAcknowledged
                    ? "Advisory acknowledged"
                    : "Acknowledge advisory"}
                </button>
              </article>

              <article className="rounded-2xl border border-slate-800 bg-slate-900 p-6">
                <h3 className="font-semibold">Today&apos;s activity</h3>
                <ul className="mt-4 space-y-4 text-sm text-slate-300">
                  <li>🟢 18 fee payments recorded</li>
                  <li>🔵 6 hostel requests received</li>
                  <li>🟣 124 exam registrations</li>
                </ul>
              </article>
            </div>
          </>
        )}

        {portal === "accounts" && (
          <>
            <p className="text-slate-400">Finance operations</p>
            <h2 className="mt-1 text-3xl font-bold">Fee Collection</h2>

            <div className="mt-8 grid gap-5 sm:grid-cols-3">
              <Card label="Collected this term" value="₹18.4L" note="+12% from last term" color="text-emerald-400" />
              <Card label="Outstanding dues" value="₹3.2L" note="148 students need follow-up" color="text-amber-300" />
              <Card label="Payments today" value="18" note="All gateway payments reconciled" />
            </div>

            <article className="mt-8 overflow-hidden rounded-2xl border border-slate-800 bg-slate-900">
              <div className="p-6">
                <h3 className="font-semibold">Recent fee records</h3>
                <p className="mt-1 text-sm text-slate-400">
                  Record a payment during the demo to show a status update.
                </p>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full min-w-[650px] text-left text-sm">
                  <thead className="border-y border-slate-800 bg-slate-800/70 text-slate-400">
                    <tr>
                      <th className="px-6 py-4">Student</th>
                      <th className="px-6 py-4">Fee Type</th>
                      <th className="px-6 py-4">Amount</th>
                      <th className="px-6 py-4">Status</th>
                      <th className="px-6 py-4">Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr className="border-b border-slate-800">
                      <td className="px-6 py-4">
                        <p className="font-medium">Aarav Mehta</p>
                        <p className="text-xs text-slate-500">STU2026012</p>
                      </td>
                      <td className="px-6 py-4">Tuition Fee</td>
                      <td className="px-6 py-4">₹42,000</td>
                      <td className="px-6 py-4">
                        <Badge tone={paymentReceived ? "green" : "amber"}>
                          {paymentReceived ? "PAID" : "PENDING"}
                        </Badge>
                      </td>
                      <td className="px-6 py-4">
                        <button
                          disabled={paymentReceived}
                          onClick={() => setPaymentReceived(true)}
                          className="rounded-lg bg-blue-600 px-3 py-2 font-medium disabled:bg-slate-700"
                        >
                          {paymentReceived
                            ? "Receipt generated"
                            : "Record payment"}
                        </button>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </article>
          </>
        )}

        {portal === "warden" && (
          <>
            <p className="text-slate-400">Hostel operations</p>
            <h2 className="mt-1 text-3xl font-bold">Hostel Allocation</h2>

            <div className="mt-8 grid gap-5 sm:grid-cols-3">
              <Card label="Total beds" value="800" note="Across 4 hostels" />
              <Card label="Allocated" value={roomAllocated ? "737" : "736"} note="92% current occupancy" color="text-emerald-400" />
              <Card label="Pending requests" value={roomAllocated ? "5" : "6"} note="Awaiting warden action" color="text-amber-300" />
            </div>

            <article className="mt-8 max-w-2xl rounded-2xl border border-slate-800 bg-slate-900 p-6">
              <h3 className="font-semibold">Allocation request</h3>

              <div className="mt-5 rounded-xl bg-slate-800/70 p-5">
                <p className="font-medium">Nikhil Verma</p>
                <p className="mt-2 text-sm text-slate-400">
                  Student ID: STU2026061
                </p>
                <p className="mt-2 text-sm text-slate-400">
                  Recommended room: Boys Hostel A — A-204
                </p>
                <p className="mt-2 text-sm text-emerald-300">
                  One bed is available.
                </p>
              </div>

              <button
                disabled={roomAllocated}
                onClick={() => setRoomAllocated(true)}
                className="mt-5 rounded-lg bg-blue-600 px-4 py-2.5 font-semibold disabled:bg-slate-700"
              >
                {roomAllocated
                  ? "Room A-204 allocated"
                  : "Allocate recommended room"}
              </button>
            </article>
          </>
        )}

        {portal === "exam" && (
          <>
            <p className="text-slate-400">Examination control</p>
            <h2 className="mt-1 text-3xl font-bold">
              Exam Registration & Eligibility
            </h2>

            <div className="mt-8 grid gap-5 sm:grid-cols-3">
              <Card label="Registrations" value={examApproved ? "1,247" : "1,246"} note="Mid-semester examinations" />
              <Card label="Eligible students" value="96%" note="Checked against attendance policy" color="text-emerald-400" />
              <Card label="Needs review" value="12" note="Attendance-related cases" color="text-amber-300" />
            </div>

            <article className="mt-8 max-w-3xl rounded-2xl border border-slate-800 bg-slate-900 p-6">
              <Badge tone="amber">Human approval required</Badge>
              <h3 className="mt-4 text-xl font-semibold">Registration review</h3>
              <p className="mt-2 text-slate-300">
                Kavya Iyer · STU2026108 · Data Structures Mid-semester
              </p>
              <p className="mt-2 text-amber-300">
                Attendance: 74% — advisor note attached
              </p>
              <p className="mt-2 text-sm text-slate-400">
                AI can flag a risk, but the exam officer makes the final decision.
              </p>

              <button
                disabled={examApproved}
                onClick={() => setExamApproved(true)}
                className="mt-5 rounded-lg bg-blue-600 px-4 py-2.5 font-semibold disabled:bg-slate-700"
              >
                {examApproved
                  ? "Registration approved"
                  : "Approve registration"}
              </button>
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

function Badge({
  children,
  tone = "blue",
}: {
  children: ReactNode;
  tone?: "blue" | "green" | "amber";
}) {
  const colors = {
    blue: "bg-blue-500/15 text-blue-300 ring-blue-400/30",
    green: "bg-emerald-500/15 text-emerald-300 ring-emerald-400/30",
    amber: "bg-amber-500/15 text-amber-300 ring-amber-400/30",
  };

  return (
    <span
      className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ring-1 ${colors[tone]}`}
    >
      {children}
    </span>
  );
}