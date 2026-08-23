"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError } from "./api";
import { getCurrentUser } from "./services";
import type { CurrentUser } from "./types";

export type AuthGuardState =
  | { status: "checking" }
  | { status: "ready"; user: CurrentUser }
  | { status: "redirecting" };

/**
 * Route guard + identity hook for protected pages.
 *
 * - No token in localStorage -> redirect to /login
 * - Token present but GET /auth/me returns 401 -> clear the stale token,
 *   redirect to /login
 * - Token valid but role isn't in `allowedRoles` -> redirect to /login
 *   (authenticated, but this isn't their portal — backend RBAC would 403
 *   any real request anyway, so there's nothing useful to show here)
 *
 * Backend roles are lowercase ("student", "faculty", ...) — pass them
 * that way, matching app/core/rbac.py's Role enum values.
 */
export function useAuthGuard(allowedRoles: string[]): AuthGuardState {
  const router = useRouter();
  const [state, setState] = useState<AuthGuardState>({ status: "checking" });

  useEffect(() => {
    let cancelled = false;

    const token =
      typeof window !== "undefined" ? localStorage.getItem("access_token") : null;

    if (!token) {
      router.replace("/login");
      setState({ status: "redirecting" });
      return;
    }

    getCurrentUser()
      .then((user) => {
        if (cancelled) return;
        if (!allowedRoles.includes(user.role)) {
          router.replace("/login");
          setState({ status: "redirecting" });
          return;
        }
        setState({ status: "ready", user });
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401 && typeof window !== "undefined") {
          localStorage.removeItem("access_token");
        }
        router.replace("/login");
        setState({ status: "redirecting" });
      });

    return () => {
      cancelled = true;
    };
    // Only run once per mount — allowedRoles is passed as a literal array
    // at each call site, re-running on identity change would loop.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return state;
}

export function logout(router: ReturnType<typeof useRouter>) {
  if (typeof window !== "undefined") {
    localStorage.removeItem("access_token");
  }
  router.push("/login");
}
