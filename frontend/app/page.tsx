import Link from "next/link";

export default function Home() {
  return (
    <main className="min-h-screen bg-slate-950 text-white">
      {/* Header */}
      <header className="border-b border-slate-800">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-5">
          <div>
            <h1 className="text-2xl font-bold">
              Campus<span className="text-blue-500">Flow</span> AI
            </h1>
            <p className="text-xs text-slate-400">
              Intelligent Campus Management
            </p>
          </div>

          <Link
            href="/login"
            className="rounded-lg bg-blue-600 px-5 py-2.5 font-medium hover:bg-blue-700"
          >
            Login
          </Link>
        </div>
      </header>

      {/* Hero */}
      <section className="mx-auto flex min-h-[70vh] max-w-7xl items-center px-6 py-20">
        <div className="max-w-3xl">
          <div className="mb-6 inline-flex rounded-full border border-blue-500/30 bg-blue-500/10 px-4 py-2 text-sm text-blue-400">
            AI-Powered Campus ERP
          </div>

          <h2 className="text-5xl font-bold leading-tight md:text-6xl">
            Smarter Campus.
            <br />
            <span className="text-blue-500">Better Management.</span>
          </h2>

          <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-400">
            CampusFlow AI connects students, faculty and campus services
            through one intelligent management platform.
          </p>

          <div className="mt-10 flex gap-4">
            <Link
              href="/login"
              className="rounded-lg bg-blue-600 px-7 py-3 font-semibold hover:bg-blue-700"
            >
              Get Started
            </Link>

            <a
              href="#features"
              className="rounded-lg border border-slate-700 px-7 py-3 font-semibold hover:bg-slate-900"
            >
              Explore Features
            </a>
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="border-t border-slate-800 bg-slate-900/50">
        <div className="mx-auto max-w-7xl px-6 py-16">
          <h3 className="text-3xl font-bold">One Platform. Every Campus.</h3>

          <div className="mt-10 grid gap-6 md:grid-cols-3">
            <Feature
              title="Student Portal"
              description="View attendance, fees, examinations, hostel information and campus notifications."
            />

            <Feature
              title="Faculty Portal"
              description="Manage student attendance, rosters, academic information and alerts."
            />

            <Feature
              title="AI Automation"
              description="Intelligent event-driven workflows help identify risks and automate campus operations."
            />
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-800 px-6 py-6 text-center text-sm text-slate-500">
        © 2026 CampusFlow AI
      </footer>
    </main>
  );
}

function Feature({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950 p-6">
      <h4 className="text-xl font-semibold">{title}</h4>
      <p className="mt-3 leading-7 text-slate-400">{description}</p>
    </div>
  );
}
