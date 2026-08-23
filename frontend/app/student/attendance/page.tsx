"use client";

export default function AttendancePage() {
  const subjects = [
    { name: "Data Structures", attended: 42, total: 48 },
    { name: "Operating Systems", attended: 38, total: 45 },
    { name: "Computer Networks", attended: 40, total: 44 },
    { name: "Database Management", attended: 35, total: 40 },
    { name: "Cyber Security", attended: 43, total: 46 },
  ];

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <nav className="border-b border-slate-800 px-6 py-5">
        <div className="mx-auto max-w-7xl">
          <h1 className="text-2xl font-bold">
            Campus<span className="text-blue-500">Flow</span> AI
          </h1>
          <p className="text-sm text-slate-400">Student Portal</p>
        </div>
      </nav>

      <section className="mx-auto max-w-7xl px-6 py-10">
        <h2 className="text-3xl font-bold">Attendance</h2>
        <p className="mt-2 text-slate-400">
          View your current subject-wise attendance.
        </p>

        <div className="mt-8 rounded-xl border border-slate-800 bg-slate-900 p-6">
          <div className="mb-6">
            <p className="text-sm text-slate-400">Overall Attendance</p>
            <p className="mt-1 text-4xl font-bold text-blue-500">87%</p>
          </div>

          <div className="space-y-5">
            {subjects.map((subject) => {
              const percentage = Math.round(
                (subject.attended / subject.total) * 100
              );

              return (
                <div key={subject.name}>
                  <div className="flex justify-between">
                    <span>{subject.name}</span>
                    <span className="text-slate-400">
                      {subject.attended}/{subject.total} ({percentage}%)
                    </span>
                  </div>

                  <div className="mt-2 h-2 rounded-full bg-slate-800">
                    <div
                      className="h-2 rounded-full bg-blue-500"
                      style={{ width: `${percentage}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </section>
    </main>
  );
}