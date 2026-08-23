export default function ExamPage() {
  const exams = [
    {
      subject: "Data Structures",
      date: "10 September 2026",
      time: "10:00 AM - 1:00 PM",
      venue: "Block A - Room 204",
      status: "Registered",
    },
    {
      subject: "Operating Systems",
      date: "13 September 2026",
      time: "10:00 AM - 1:00 PM",
      venue: "Block B - Room 301",
      status: "Registered",
    },
    {
      subject: "Computer Networks",
      date: "17 September 2026",
      time: "2:00 PM - 5:00 PM",
      venue: "Block A - Room 105",
      status: "Pending",
    },
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
        <h2 className="text-3xl font-bold">Examinations</h2>
        <p className="mt-2 text-slate-400">
          View your upcoming examinations and registration status.
        </p>

        <div className="mt-8 grid gap-6 md:grid-cols-3">
          {exams.map((exam) => (
            <div
              key={exam.subject}
              className="rounded-xl border border-slate-800 bg-slate-900 p-6"
            >
              <h3 className="text-xl font-semibold">{exam.subject}</h3>

              <div className="mt-5 space-y-3 text-sm">
                <p>
                  <span className="text-slate-500">Date: </span>
                  {exam.date}
                </p>

                <p>
                  <span className="text-slate-500">Time: </span>
                  {exam.time}
                </p>

                <p>
                  <span className="text-slate-500">Venue: </span>
                  {exam.venue}
                </p>
              </div>

              <div className="mt-6 border-t border-slate-800 pt-4">
                <span
                  className={
                    exam.status === "Registered"
                      ? "text-green-400"
                      : "text-yellow-400"
                  }
                >
                  ● {exam.status}
                </span>
              </div>
            </div>
          ))}
        </div>

        <div className="mt-8 rounded-xl border border-blue-500/30 bg-blue-500/10 p-6">
          <h3 className="text-lg font-semibold text-blue-400">
            Examination Registration
          </h3>

          <p className="mt-2 text-slate-400">
            Make sure you complete examination registration before the
            registration deadline.
          </p>

          <button className="mt-5 rounded-lg bg-blue-600 px-5 py-2.5 font-medium hover:bg-blue-700">
            Register for Examination
          </button>
        </div>
      </section>
    </main>
  );
}