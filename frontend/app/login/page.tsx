"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, ApiError } from "../../lib/api";

export default function LoginPage() {
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();

    setLoading(true);
    setError("");

    try {
      const data = await apiFetch("/auth/login", {
        method: "POST",
        body: JSON.stringify({
          email,
          password,
        }),
      });

      localStorage.setItem("access_token", data.access_token);

      const user = await apiFetch("/auth/me");

      // Backend issues/returns roles lowercase (see app/core/rbac.py's
      // Role enum values: "student", "faculty", "admin", "accounts",
      // "warden", "exam_officer") -- match that here.
      const destination: Record<string, string> = {
        student: "/student/dashboard",
        faculty: "/faculty/dashboard",
        admin: "/admin/dashboard",
        accounts: "/accounts/dashboard",
        warden: "/warden/dashboard",
        exam_officer: "/exam/dashboard",
      };

      const path = destination[user.role];

      if (path) {
        router.push(path);
      } else {
        setError("This portal is not assigned to your role.");
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError("Invalid email or password.");
      } else if (err instanceof ApiError) {
        setError(err.message || "Something went wrong. Please try again.");
      } else {
        setError("Could not reach the server. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <main
      style={{
        minHeight: "100vh",
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        background: "#f5f7fb",
      }}
    >
      <form
        onSubmit={handleLogin}
        style={{
          width: 400,
          padding: 30,
          background: "white",
          borderRadius: 12,
          boxShadow: "0 5px 25px rgba(0,0,0,0.1)",
        }}
      >
        <h1>CampusFlow AI</h1>

        <p>Sign in to your portal</p>

        <br />

        <label>Email</label>

        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          style={{
            width: "100%",
            padding: 12,
            marginTop: 5,
            marginBottom: 15,
          }}
        />

        <label>Password</label>

        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          style={{
            width: "100%",
            padding: 12,
            marginTop: 5,
            marginBottom: 15,
          }}
        />

        {error && (
          <p style={{ color: "red" }}>
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={loading}
          style={{
            width: "100%",
            padding: 12,
            background: "#2563eb",
            color: "white",
            border: "none",
            borderRadius: 8,
            cursor: "pointer",
          }}
        >
          {loading ? "Signing in..." : "Login"}
        </button>
      </form>
    </main>
  );
}