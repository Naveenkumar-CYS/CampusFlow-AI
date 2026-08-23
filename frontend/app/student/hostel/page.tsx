export default function HostelPage() {
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
        <h2 className="text-3xl font-bold">Hostel</h2>
        <p className="mt-2 text-slate-400">
          View your hostel allocation and accommodation details.
        </p>

        <div className="mt-8 grid gap-6 md:grid-cols-3">
          <div className="rounded-xl border border-slate-800 bg-slate-900 p-6">
            <p className="text-sm text-slate-400">Block</p>
            <p className="mt-2 text-2xl font-bold">Block A</p>
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-900 p-6">
            <p className="text-sm text-slate-400">Room</p>
            <p className="mt-2 text-2xl font-bold">A-204</p>
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-900 p-6">
            <p className="text-sm text-slate-400">Room Type</p>
            <p className="mt-2 text-2xl font-bold">4 Sharing</p>
          </div>
        </div>

        <div className="mt-8 rounded-xl border border-slate-800 bg-slate-900 p-6">
          <h3 className="text-xl font-semibold">Room Members</h3>

          <div className="mt-5 space-y-3">
            {["Arun Kumar", "Rahul Sharma", "Vignesh R"].map((student) => (
              <div
                key={student}
                className="flex items-center justify-between rounded-lg bg-slate-800 p-4"
              >
                <span>{student}</span>
                <span className="text-sm text-green-400">Active</span>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-8 rounded-xl border border-slate-800 bg-slate-900 p-6">
          <h3 className="text-xl font-semibold">Hostel Request</h3>

          <p className="mt-2 text-slate-400">
            Need a room change or have a hostel-related request?
          </p>

          <button className="mt-5 rounded-lg bg-blue-600 px-5 py-2.5 font-medium hover:bg-blue-700">
            Submit Request
          </button>
        </div>
      </section>
    </main>
  );
}