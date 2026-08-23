"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "../../../lib/api";

export default function StudentDashboard() {
  const [user, setUser] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch("/auth/me")
      .then(setUser)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div style={{ padding: 40 }}>Loading...</div>;
  }

  return (
    <main style={{ padding: 40 }}>
      <h1>Student Dashboard</h1>

      <p>
        Welcome, {user?.email || "Student"}
      </p>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gap: 20,
          marginTop: 30,
        }}
      >
        <DashboardCard
          title="Attendance"
          value="--"
        />

        <DashboardCard
          title="Fees Due"
          value="₹ --"
        />

        <DashboardCard
          title="Hostel"
          value="--"
        />

        <DashboardCard
          title="Exams"
          value="--"
        />
      </div>
    </main>
  );
}

function DashboardCard({
  title,
  value,
}: {
  title: string;
  value: string;
}) {
  return (
    <div
      style={{
        background: "white",
        padding: 25,
        borderRadius: 12,
        boxShadow: "0 2px 10px rgba(0,0,0,0.08)",
      }}
    >
      <p style={{ color: "#6b7280" }}>{title}</p>
      <h2>{value}</h2>
    </div>
  );
}