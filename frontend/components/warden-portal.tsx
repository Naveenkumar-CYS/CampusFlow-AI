"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { LoadingState, ErrorState, EmptyState } from "./portal-ui";
import { useAuthGuard, logout } from "../lib/auth";
import {
  createHostelAllocation,
  listHostelAllocations,
  listHostels,
  listRooms,
  listStudents,
  updateHostelAllocation,
} from "../lib/services";
import { ApiError } from "../lib/api";
import type { Allocation, Hostel, Room, StudentRead } from "../lib/types";

// Same 4-tab layout as the rest of the staff portals (components/accounts-portal.tsx)
// — this file only owns the "warden" tab's content and data.
const NAV = [
  { key: "admin", label: "Admin", href: "/admin/dashboard" },
  { key: "accounts", label: "Accounts", href: "/accounts/dashboard" },
  { key: "warden", label: "Warden", href: "/warden/dashboard" },
  { key: "exam", label: "Examinations", href: "/exam/dashboard" },
];

type DataState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | {
      status: "ready";
      hostels: Hostel[];
      rooms: Room[];
      allocations: Allocation[];
      students: StudentRead[];
    };

export function WardenPortal() {
  const router = useRouter();
  // WARDEN owns hostel allocation; ADMIN also has staff access to the same
  // /hostel endpoints per backend RBAC (app/api/hostel.py _FACILITY_STAFF),
  // so both are allowed in here — same pattern as the accounts portal.
  const guard = useAuthGuard(["warden", "admin"]);

  const [state, setState] = useState<DataState>({ status: "loading" });
  const [selectedStudent, setSelectedStudent] = useState("");
  const [selectedRoom, setSelectedRoom] = useState("");
  const [allocateError, setAllocateError] = useState<string | null>(null);
  const [allocateSubmitting, setAllocateSubmitting] = useState(false);
  const [vacatingId, setVacatingId] = useState<string | null>(null);

  function load() {
    setState({ status: "loading" });
    Promise.all([listHostels(), listRooms(), listHostelAllocations(), listStudents()])
      .then(([hostels, rooms, allocations, students]) =>
        setState({ status: "ready", hostels, rooms, allocations, students })
      )
      .catch((err) =>
        setState({
          status: "error",
          message: err instanceof ApiError ? err.message : "Failed to load hostel records.",
        })
      );
  }

  useEffect(() => {
    if (guard.status === "ready") load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [guard.status]);

  const hostels = state.status === "ready" ? state.hostels : [];
  const rooms = state.status === "ready" ? state.rooms : [];
  const allocations = state.status === "ready" ? state.allocations : [];
  const students = state.status === "ready" ? state.students : [];

  const hostelById = new Map(hostels.map((h) => [h.id, h]));
  const studentByPk = new Map(students.map((s) => [s.id, s]));
  const roomById = new Map(rooms.map((r) => [r.id, r]));

  const activeAllocations = allocations.filter((a) => a.status === "ACTIVE");
  const allocatedStudentPks = new Set(activeAllocations.map((a) => a.student_id));

  const totalBeds = rooms.reduce((sum, r) => sum + r.capacity, 0);
  const occupiedBeds = rooms.reduce((sum, r) => sum + r.current_occupancy, 0);
  const availableBeds = totalBeds - occupiedBeds;
  const occupancyRate = totalBeds > 0 ? Math.round((occupiedBeds / totalBeds) * 100) : 0;

  // Only students without a current ACTIVE allocation can be allocated a room.
  const unallocatedStudents = students.filter((s) => !allocatedStudentPks.has(s.id));
  // Only rooms with free capacity can be selected.
  const availableRooms = rooms.filter((r) => r.current_occupancy < r.capacity);

  const sortedAllocations = activeAllocations
    .slice()
    .sort((a, b) => (a.created_at < b.created_at ? 1 : -1));

  async function submitAllocation() {
    if (!selectedStudent || !selectedRoom) {
      setAllocateError("Choose a student and a room.");
      return;
    }
    setAllocateSubmitting(true);
    setAllocateError(null);
    try {
      await createHostelAllocation({ student_id: selectedStudent, room_id: selectedRoom });
      setSelectedStudent("");
      setSelectedRoom("");
      load();
    } catch (err) {
      setAllocateError(err instanceof ApiError ? err.message : "Failed to allocate room.");
    } finally {
      setAllocateSubmitting(false);
    }
  }

  async function vacate(allocationId: string) {
    setVacatingId(allocationId);
    try {
      await updateHostelAllocation(allocationId, { status: "VACATED" });
      load();
    } catch {
      // Surface via the general error state on next load if it's systemic;
      // a single failed vacate just leaves the row actionable again.
    } finally {
      setVacatingId(null);
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
            <p className="text-sm text-slate-400">Warden Portal</p>
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
                item.key === "warden"
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
        <p className="text-slate-400">Hostel operations</p>
        <h2 className="mt-1 text-3xl font-bold">Hostel Allocation</h2>

        {guard.status !== "ready" && <LoadingState label="Checking your session..." />}

        {guard.status === "ready" && state.status === "loading" && (
          <LoadingState label="Loading hostel records..." />
        )}

        {guard.status === "ready" && state.status === "error" && (
          <ErrorState message={state.message} onRetry={load} />
        )}

        {guard.status === "ready" && state.status === "ready" && (
          <>
            <div className="mt-8 grid gap-5 sm:grid-cols-3">
              <Card label="Total beds" value={String(totalBeds)} note={`Across ${hostels.length} hostel${hostels.length === 1 ? "" : "s"}`} />
              <Card
                label="Allocated"
                value={String(occupiedBeds)}
                note={`${occupancyRate}% current occupancy`}
                color="text-emerald-400"
              />
              <Card label="Available beds" value={String(availableBeds)} note="Open for allocation" color="text-amber-300" />
            </div>

            <article className="mt-8 max-w-2xl rounded-2xl border border-slate-800 bg-slate-900 p-6">
              <h3 className="font-semibold">Allocate a room</h3>
              <p className="mt-1 text-sm text-slate-400">
                Pick a student without a current allocation and a room with a free bed.
              </p>

              {unallocatedStudents.length === 0 ? (
                <p className="mt-4 text-sm text-slate-500">
                  Every student currently has an active hostel allocation.
                </p>
              ) : availableRooms.length === 0 ? (
                <p className="mt-4 text-sm text-slate-500">No rooms have a free bed right now.</p>
              ) : (
                <div className="mt-5 flex flex-col gap-3">
                  <select
                    value={selectedStudent}
                    onChange={(e) => setSelectedStudent(e.target.value)}
                    className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white"
                  >
                    <option value="">Select student...</option>
                    {unallocatedStudents.map((s) => (
                      <option key={s.id} value={s.student_id}>
                        {s.name} — {s.student_id}
                      </option>
                    ))}
                  </select>

                  <select
                    value={selectedRoom}
                    onChange={(e) => setSelectedRoom(e.target.value)}
                    className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white"
                  >
                    <option value="">Select room...</option>
                    {availableRooms.map((r) => {
                      const hostel = hostelById.get(r.hostel_id);
                      return (
                        <option key={r.id} value={r.id}>
                          {hostel?.name ?? hostel?.hostel_code ?? "Hostel"} — {r.room_number} (
                          {r.current_occupancy}/{r.capacity})
                        </option>
                      );
                    })}
                  </select>

                  {allocateError && <p className="text-xs text-red-400">{allocateError}</p>}

                  <button
                    disabled={allocateSubmitting}
                    onClick={submitAllocation}
                    className="rounded-lg bg-blue-600 px-4 py-2.5 font-semibold hover:bg-blue-700 disabled:bg-slate-700"
                  >
                    {allocateSubmitting ? "Allocating..." : "Allocate room"}
                  </button>
                </div>
              )}
            </article>

            <article className="mt-8 overflow-hidden rounded-2xl border border-slate-800 bg-slate-900">
              <div className="p-6">
                <h3 className="font-semibold">Active allocations</h3>
                <p className="mt-1 text-sm text-slate-400">
                  Vacate an allocation to free the bed for a new student.
                </p>
              </div>

              {sortedAllocations.length === 0 ? (
                <div className="px-6 pb-6">
                  <EmptyState message="No active hostel allocations yet." />
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[650px] text-left text-sm">
                    <thead className="border-y border-slate-800 bg-slate-800/70 text-slate-400">
                      <tr>
                        <th className="px-6 py-4">Student</th>
                        <th className="px-6 py-4">Hostel</th>
                        <th className="px-6 py-4">Room</th>
                        <th className="px-6 py-4">Allocated</th>
                        <th className="px-6 py-4">Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sortedAllocations.map((allocation) => {
                        const student = studentByPk.get(allocation.student_id);
                        const room = roomById.get(allocation.room_id);
                        const hostel = room ? hostelById.get(room.hostel_id) : undefined;
                        const isVacating = vacatingId === allocation.id;

                        return (
                          <tr key={allocation.id} className="border-b border-slate-800 last:border-0">
                            <td className="px-6 py-4">
                              <p className="font-medium">{student?.name ?? "Unknown student"}</p>
                              <p className="text-xs text-slate-500">{student?.student_id ?? "—"}</p>
                            </td>
                            <td className="px-6 py-4">{hostel?.name ?? hostel?.hostel_code ?? "—"}</td>
                            <td className="px-6 py-4">{room?.room_number ?? "—"}</td>
                            <td className="px-6 py-4 text-slate-400">
                              {new Date(allocation.created_at).toLocaleDateString("en-IN")}
                            </td>
                            <td className="px-6 py-4">
                              <button
                                disabled={isVacating}
                                onClick={() => vacate(allocation.id)}
                                className="rounded-lg border border-slate-700 px-3 py-2 text-xs font-medium hover:bg-slate-800 disabled:opacity-50"
                              >
                                {isVacating ? "Vacating..." : "Vacate"}
                              </button>
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
