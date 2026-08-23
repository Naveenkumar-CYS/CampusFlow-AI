"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { logout } from "../lib/auth";

const STUDENT_NAV = [
  { key: "dashboard", label: "Dashboard", href: "/student/dashboard" },
  { key: "attendance", label: "Attendance", href: "/student/attendance" },
  { key: "fees", label: "Fees", href: "/student/fees" },
  { key: "hostel", label: "Hostel", href: "/student/hostel" },
  { key: "exam", label: "Examinations", href: "/student/exam" },
  { key: "profile", label: "Profile", href: "/student/profile" },
];

const FACULTY_NAV = [
  { key: "dashboard", label: "Dashboard", href: "/faculty/dashboard" },
  { key: "students", label: "Students", href: "/faculty/students" },
  { key: "attendance", label: "Attendance", href: "/faculty/attendance" },
];

export function PortalHeader({
  portal,
  active,
}: {
  portal: "student" | "faculty";
  active: string;
}) {
  const router = useRouter();
  const nav = portal === "student" ? STUDENT_NAV : FACULTY_NAV;

  return (
    <>
      <nav className="border-b border-slate-800 px-6 py-5">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">
              Campus<span className="text-blue-500">Flow</span> AI
            </h1>
            <p className="text-sm text-slate-400">
              {portal === "student" ? "Student Portal" : "Faculty Portal"}
            </p>
          </div>

          <button
            onClick={() => logout(router)}
            className="rounded-lg border border-slate-700 px-4 py-2 text-sm hover:bg-slate-800"
          >
            Logout
          </button>
        </div>
      </nav>

      <div className="border-b border-slate-800 bg-slate-900/50">
        <div className="mx-auto flex max-w-7xl gap-2 overflow-x-auto px-6 py-3">
          {nav.map((item) => (
            <Link
              key={item.key}
              href={item.href}
              className={`whitespace-nowrap rounded-lg px-4 py-2 text-sm font-medium ${
                item.key === active
                  ? "bg-blue-600 text-white"
                  : "text-slate-300 hover:bg-slate-800"
              }`}
            >
              {item.label}
            </Link>
          ))}
        </div>
      </div>
    </>
  );
}

export function LoadingState({ label = "Loading..." }: { label?: string }) {
  return (
    <div className="mt-8 rounded-xl border border-slate-800 bg-slate-900 p-10 text-center text-slate-400">
      {label}
    </div>
  );
}

export function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="mt-8 rounded-xl border border-red-500/30 bg-red-500/10 p-6 text-red-200">
      <p className="font-semibold">Something went wrong</p>
      <p className="mt-1 text-sm text-red-200/80">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-4 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700"
        >
          Retry
        </button>
      )}
    </div>
  );
}

export function EmptyState({ message }: { message: string }) {
  return (
    <div className="mt-8 rounded-xl border border-slate-800 bg-slate-900 p-10 text-center text-slate-400">
      {message}
    </div>
  );
}

/**
 * Shown when a page needs something the backend genuinely has no
 * endpoint for yet — distinct from ErrorState because nothing is
 * broken; it's a documented, known gap (see the session's final report).
 */
export function BackendDependencyNotice({
  title,
  detail,
}: {
  title: string;
  detail: string;
}) {
  return (
    <div className="mt-8 rounded-xl border border-amber-500/30 bg-amber-500/10 p-6 text-amber-100">
      <p className="font-semibold text-amber-200">{title}</p>
      <p className="mt-2 text-sm leading-6 text-amber-100/80">{detail}</p>
    </div>
  );
}
