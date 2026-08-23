export default function FacultyDashboard() {
  const cards = [
    {
      title: "Students",
      value: "128",
      description: "Students assigned",
      href: "/faculty/students",
    },
    {
      title: "Attendance",
      value: "92%",
      description: "Today's attendance",
      href: "/faculty/attendance",
    },
    {
      title: "Pending Tasks",
      value: "7",
      description: "Tasks requiring attention",
    },
    {
      title: "Alerts",
      value: "3",
      description: "Student alerts",
    },
  ];

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <nav className="border-b border-slate-800 px-6 py-5">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">
              Campus<span className="text-blue-500">Flow</span> AI
            </h1>
            <p className="text-sm text-slate-400">Faculty Portal</p>
          </div>

          <a
            href="/login"
            className="rounded-lg border border-slate-700 px-4 py-2 hover:bg-slate-800"
          >
            Logout
          </a>
        </div>
      </nav>

      <section className="mx-auto max-w-7xl px-6 py-10">
        <p className="text-slate-400">Welcome back,</p>
        <h2 className="mt-1 text-3xl font-bold">Faculty Dashboard</h2>

        <div className="mt-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {cards.map((card) => (
            <a
              key={card.title}
              href={card.href}
              className="rounded-xl border border-slate-800 bg-slate-900 p-6 transition hover:-translate-y-1 hover:border-blue-500"
            >
              <p className="text-slate-400">{card.title}</p>

              <p className="mt-3 text-3xl font-bold text-blue-500">
                {card.value}
              </p>

              <p className="mt-2 text-sm text-slate-500">
                {card.description}
              </p>
            </a>
          ))}
        </div>

        <div className="mt-10 rounded-xl border border-blue-500/30 bg-blue-500/10 p-6">
          <h3 className="text-xl font-semibold text-blue-400">
            AI Advisory
          </h3>

          <p className="mt-3 text-slate-300">
            5 students have attendance below the recommended threshold.
            Review their attendance and take appropriate action.
          </p>

          <a
            href="/faculty/attendance"
            className="mt-5 inline-block rounded-lg bg-blue-600 px-5 py-2.5 font-medium hover:bg-blue-700"
          >
            Review Attendance
          </a>
        </div>
      </section>
    </main>
  );
}