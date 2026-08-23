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
import { listHostelAllocations, listHostels, listRooms } from "../../../lib/services";
import { ApiError } from "../../../lib/api";
import type { Allocation, Hostel, Room } from "../../../lib/types";

type HostelState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; allocation: Allocation | null; room: Room | null; hostel: Hostel | null };

export default function HostelPage() {
  const guard = useAuthGuard(["student"]);
  const user = guard.status === "ready" ? guard.user : null;
  const studentState = useOwnStudent(user);

  const [state, setState] = useState<HostelState>({ status: "loading" });

  function load(code: string) {
    setState({ status: "loading" });
    listHostelAllocations({ student_id: code })
      .then(async (allocations) => {
        const allocation = allocations.find((a) => a.status === "ACTIVE") ?? null;
        if (!allocation) {
          setState({ status: "ready", allocation: null, room: null, hostel: null });
          return;
        }
        const [rooms, hostels] = await Promise.all([listRooms(), listHostels()]);
        const room = rooms.find((r) => r.id === allocation.room_id) ?? null;
        const hostel = room ? hostels.find((h) => h.id === room.hostel_id) ?? null : null;
        setState({ status: "ready", allocation, room, hostel });
      })
      .catch((err) =>
        setState({
          status: "error",
          message: err instanceof ApiError ? err.message : "Failed to load hostel information.",
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
      <PortalHeader portal="student" active="hostel" />

      <section className="mx-auto max-w-7xl px-6 py-10">
        <h2 className="text-3xl font-bold">Hostel</h2>
        <p className="mt-2 text-slate-400">View your hostel allocation and accommodation details.</p>

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
            {state.status === "loading" && <LoadingState label="Loading hostel information..." />}

            {state.status === "error" && (
              <ErrorState
                message={state.message}
                onRetry={() => load(studentState.student.student_id)}
              />
            )}

            {state.status === "ready" && !state.allocation && (
              <EmptyState message="You don't have an active hostel allocation." />
            )}

            {state.status === "ready" && state.allocation && (
              <>
                <div className="mt-8 grid gap-6 md:grid-cols-3">
                  <InfoCard label="Hostel" value={state.hostel?.name ?? "Unknown"} />
                  <InfoCard label="Room" value={state.room?.room_number ?? "Unknown"} />
                  <InfoCard
                    label="Occupancy"
                    value={
                      state.room ? `${state.room.current_occupancy}/${state.room.capacity}` : "Unknown"
                    }
                  />
                </div>

                <div className="mt-8 rounded-xl border border-slate-800 bg-slate-900 p-6">
                  <h3 className="text-xl font-semibold">Allocation Status</h3>
                  <p className="mt-3 text-green-400">● {state.allocation.status}</p>
                  <p className="mt-2 text-sm text-slate-400">
                    Since {new Date(state.allocation.created_at).toLocaleDateString()}
                  </p>
                </div>
              </>
            )}
          </>
        )}

        <BackendDependencyNotice
          title="Hostel change requests aren't wired up"
          detail="The backend has no request/ticket concept for hostel changes — allocations are only ever created or updated by ADMIN/WARDEN. A 'Submit Request' button here would have nothing real to call, so it isn't shown; this is left as a documented remaining item rather than a fake action."
        />
      </section>
    </main>
  );
}

function InfoCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-6">
      <p className="text-sm text-slate-400">{label}</p>
      <p className="mt-2 text-2xl font-bold">{value}</p>
    </div>
  );
}
