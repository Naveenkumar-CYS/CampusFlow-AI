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

export function useAuthGuard(allowedRoles: string[]): AuthGuardState {
  const router = useRouter();
  const [state, setState] = useState<AuthGuardState>({
    status: "checking",
  });

  useEffect(() => {
    let cancelled = false;

    const token =
      typeof window !== "undefined"
        ? localStorage.getItem("access_token")
        : null;

    if (!token) {
      console.error("AUTH GUARD: TOKEN MISSING");
      router.replace("/login");
      setState({ status: "redirecting" });
      return;
    }

    getCurrentUser()
      .then((user) => {
        if (cancelled) return;

        const normalizedRole = user.role.toLowerCase();

        console.log("AUTH GUARD DEBUG:", {
          userRole: user.role,
          normalizedRole,
          allowedRoles,
          token: localStorage.getItem("access_token")
            ? "PRESENT"
            : "MISSING",
        });

        if (
          !allowedRoles.some(
            (role) => role.toLowerCase() === normalizedRole
          )
        ) {
          console.error("AUTH GUARD: ROLE MISMATCH");
          router.replace("/login");
          setState({ status: "redirecting" });
          return;
        }

        console.log("AUTH GUARD: ROLE ACCEPTED");
        setState({ status: "ready", user });
      })
      .catch((err) => {
        console.error("AUTH GUARD: getCurrentUser FAILED", err);

        if (cancelled) return;

        if (
          err instanceof ApiError &&
          err.status === 401 &&
          typeof window !== "undefined"
        ) {
          localStorage.removeItem("access_token");
        }

        router.replace("/login");
        setState({ status: "redirecting" });
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}

export function logout(router: ReturnType<typeof useRouter>) {
  if (typeof window !== "undefined") {
    localStorage.removeItem("access_token");
  }

  router.push("/login");
}