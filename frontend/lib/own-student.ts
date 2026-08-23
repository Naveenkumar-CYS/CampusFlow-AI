"use client";

import { useEffect, useState } from "react";
import { ApiError } from "./api";
import { getOwnStudent } from "./services";
import type { CurrentUser, StudentRead } from "./types";

export type OwnStudentState =
  | { status: "loading" }
  | { status: "ready"; student: StudentRead }
  // The authenticated account has no linked Student row (GET /students/me
  // returns 404). Distinct from a network/server error.
  | { status: "unresolvable" }
  | { status: "error"; message: string };

export function useOwnStudent(user: CurrentUser | null): OwnStudentState {
  const [state, setState] = useState<OwnStudentState>({ status: "loading" });

  useEffect(() => {
    if (!user) return;
    let cancelled = false;

    setState({ status: "loading" });
    getOwnStudent()
      .then((student) => {
        if (!cancelled) setState({ status: "ready", student });
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 404) {
          setState({ status: "unresolvable" });
          return;
        }
        setState({
          status: "error",
          message: err instanceof ApiError ? err.message : "Failed to load your student record.",
        });
      });

    return () => {
      cancelled = true;
    };
  }, [user]);

  return state;
}
