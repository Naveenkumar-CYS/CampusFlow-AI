"use client";

import { useState } from "react";

const initialStudents = [
  { id: "STU001", name: "Arun Kumar", present: true },
  { id: "STU002", name: "Rahul Sharma", present: true },
  { id: "STU003", name: "Vignesh R", present: false },
  { id: "STU004", name: "Karthik S", present: true },
  { id: "STU005", name: "Sanjay Kumar", present: true },
];

export default function FacultyAttendancePage() {
  const [students, setStudents] = useState(initialStudents);

  const toggleAttendance = (id: string) => {
    setStudents((current) =>
      current.map((student) =>
        student.id === id
          ? { ...student, present: !student.present }
          : student
      )
    );
  };

  const presentCount = students.filter((student) => student.present).length;

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <nav className="border-b border-slate-800 px-6 py-5">
        <div className="mx-auto max-w-7xl">
          <h1 className="text-2xl font-bold">
            Campus<span className="text-blue-500">Flow</span> AI
          </h1>
          <p className="text-sm text-slate-400">Faculty Portal</p>
        </div>
      </nav>

      <section className="mx-auto max-w-7xl px-6 py-10">
        <h2 className="text-3xl font-bold">Mark Attendance</h2>

        <p className="mt-2 text-slate-400">
          Mark today's attendance for your students.
        </p>

        <div className="mt-8 grid gap-4 sm:grid-cols-3">
          <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
            <p className="text-sm text-slate-400">Total Students</p>
            <p className="mt-2 text-3xl font-bold">{students.length}</p>
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
            <p className="text-sm text-slate-400">Present</p>
            <p className="mt-2 text-3xl font-bold text-green-400">
              {presentCount}
            </p>
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
            <p className="text-sm text-slate-400">Absent</p>
            <p className="mt-2 text-3xl font-bold text-red-400">
              {students.length - presentCount}
            </p>
          </div>
        </div>

        <div className="mt-8 overflow-hidden rounded-xl border border-slate-800 bg-slate-900">
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead className="bg-slate-800">
                <tr>
                  <th className="px-6 py-4">Student ID</th>
                  <th className="px-6 py-4">Student Name</th>
                  <th className="px-6 py-4">Attendance</th>
                  <th className="px-6 py-4">Action</th>
                </tr>
              </thead>

              <tbody>
                {students.map((student) => (
                  <tr
                    key={student.id}
                    className="border-t border-slate-800"
                  >
                    <td className="px-6 py-4 text-slate-400">
                      {student.id}
                    </td>

                    <td className="px-6 py-4 font-medium">
                      {student.name}
                    </td>

                    <td className="px-6 py-4">
                      <span
                        className={
                          student.present
                            ? "text-green-400"
                            : "text-red-400"
                        }
                      >
                        {student.present ? "Present" : "Absent"}
                      </span>
                    </td>

                    <td className="px-6 py-4">
                      <button
                        onClick={() => toggleAttendance(student.id)}
                        className={
                          student.present
                            ? "rounded-lg bg-red-600 px-4 py-2 font-medium hover:bg-red-700"
                            : "rounded-lg bg-green-600 px-4 py-2 font-medium hover:bg-green-700"
                        }
                      >
                        {student.present ? "Mark Absent" : "Mark Present"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <button
          onClick={() => alert("Attendance saved successfully!")}
          className="mt-6 rounded-lg bg-blue-600 px-6 py-3 font-semibold hover:bg-blue-700"
        >
          Save Attendance
        </button>
      </section>
    </main>
  );
}