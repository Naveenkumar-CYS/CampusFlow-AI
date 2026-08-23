export default function FeesPage() {
  const payments = [
    {
      semester: "Semester 6",
      description: "Tuition Fee",
      amount: "₹45,000",
      status: "Pending",
    },
    {
      semester: "Semester 6",
      description: "Hostel Fee",
      amount: "₹35,000",
      status: "Paid",
    },
    {
      semester: "Semester 5",
      description: "Tuition Fee",
      amount: "₹45,000",
      status: "Paid",
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
        <h2 className="text-3xl font-bold">Fees</h2>
        <p className="mt-2 text-slate-400">
          View your fee status and payment history.
        </p>

        <div className="mt-8 grid gap-6 md:grid-cols-3">
          <div className="rounded-xl border border-slate-800 bg-slate-900 p-6">
            <p className="text-sm text-slate-400">Total Fees</p>
            <p className="mt-2 text-3xl font-bold">₹80,000</p>
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-900 p-6">
            <p className="text-sm text-slate-400">Paid</p>
            <p className="mt-2 text-3xl font-bold text-green-500">₹35,000</p>
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-900 p-6">
            <p className="text-sm text-slate-400">Pending</p>
            <p className="mt-2 text-3xl font-bold text-red-500">₹45,000</p>
          </div>
        </div>

        <div className="mt-8 overflow-hidden rounded-xl border border-slate-800 bg-slate-900">
          <div className="border-b border-slate-800 p-6">
            <h3 className="text-xl font-semibold">Payment History</h3>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead className="bg-slate-800">
                <tr>
                  <th className="px-6 py-4">Semester</th>
                  <th className="px-6 py-4">Description</th>
                  <th className="px-6 py-4">Amount</th>
                  <th className="px-6 py-4">Status</th>
                </tr>
              </thead>

              <tbody>
                {payments.map((payment, index) => (
                  <tr
                    key={index}
                    className="border-t border-slate-800"
                  >
                    <td className="px-6 py-4">{payment.semester}</td>
                    <td className="px-6 py-4">{payment.description}</td>
                    <td className="px-6 py-4">{payment.amount}</td>
                    <td className="px-6 py-4">
                      <span
                        className={
                          payment.status === "Paid"
                            ? "text-green-400"
                            : "text-red-400"
                        }
                      >
                        {payment.status}
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