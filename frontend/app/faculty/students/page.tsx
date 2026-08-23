const students = [
  {
    id: "STU001",
    name: "Arun Kumar",
    department: "CSE",
    year: "3rd Year",
    attendance: "91%",
    status: "Good",
  },
  {
    id: "STU002",
    name: "Rahul Sharma",
    department: "CSE",
    year: "3rd Year",
    attendance: "84%",
    status: "Good",
  },
  {
    id: "STU003",
    name: "Vignesh R",
    department: "CSE",
    year: "3rd Year",
    attendance: "68%",
    status: "At Risk",
  },
  {
    id: "STU004",
    name: "Karthik S",
    department: "CSE",
    year: "3rd Year",
    attendance: "76%",
    status: "Warning",
  },
];

export default function FacultyStudentsPage() {
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
        <h2 className="text-3xl font-bold">Students</h2>
        <p className="mt-2 text-slate-400">
          View students assigned to you and their academic information.
        </p>

        <div className="mt-8 overflow-hidden rounded-xl border border-slate-800 bg-slate-900">
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead className="bg-slate-800">
                <tr>
                  <th className="px-6 py-4">ID</th>
                  <th className="px-6 py-4">Student</th>
                  <th className="px-6 py-4">Department</th>
                  <th className="px-6 py-4">Year</th>
                  <th className="px-6 py-4">Attendance</th>
                  <th className="px-6 py-4">Status</th>
                </tr>
              </thead>

              <tbody>
                {students.map((student) => (
                  <tr
                    key={student.id}
                    className="border-t border-slate-800 hover:bg-slate-800/50"
                  >
                    <td className="px-6 py-4 text-slate-400">
                      {student.id}
                    </td>

                    <td className="px-6 py-4 font-medium">
                      {student.name}
                    </td>

                    <td className="px-6 py-4">
                      {student.department}
                    </td>

                    <td className="px-6 py-4">
                      {student.year}
                    </td>

                    <td className="px-6 py-4">
                      {student.attendance}
                    </td>

                    <td className="px-6 py-4">
                      <span
                        className={
                          student.status === "Good"
                            ? "text-green-400"
                            : student.status === "Warning"
                              ? "text-yellow-400"
                              : "text-red-400"
                        }
                      >
                        ● {student.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </main>
  );
}