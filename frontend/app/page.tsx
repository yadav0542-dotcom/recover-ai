import { BackendStatus } from "@/components/backend-status";

const kpis = [
  ["Recovery rate", "—", "Awaiting payment data"],
  ["Revenue recovered", "₹ —", "Foundation stage"],
  ["Open cases", "—", "No workflow connected"],
];

export default function Home() {
  return (
    <main className="min-h-screen bg-slate-950 px-6 py-8 sm:px-10">
      <div className="mx-auto max-w-6xl">
        <header className="flex flex-col gap-5 border-b border-slate-800 pb-8 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-xl bg-cyan-400 font-black text-slate-950">R</div>
            <span className="text-lg font-semibold tracking-tight">RecoverAI</span>
          </div>
          <BackendStatus />
        </header>

        <section className="py-12">
          <p className="mb-3 text-sm font-semibold uppercase tracking-[0.18em] text-cyan-300">Revenue operations</p>
          <h1 className="max-w-3xl text-4xl font-semibold tracking-tight text-white sm:text-5xl">AI Revenue Recovery Console</h1>
          <p className="mt-4 max-w-2xl text-lg leading-8 text-slate-400">A safe workspace for future payment recovery and reconciliation operations.</p>
        </section>

        <section className="grid gap-4 md:grid-cols-3">
          {kpis.map(([label, value, detail]) => (
            <article key={label} className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5 shadow-sm">
              <p className="text-sm text-slate-400">{label}</p>
              <p className="mt-4 text-3xl font-semibold text-white">{value}</p>
              <p className="mt-2 text-sm text-slate-500">{detail}</p>
            </article>
          ))}
        </section>

        <section className="mt-6 rounded-2xl border border-slate-800 bg-slate-900/70 p-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-white">Transactions & recovery queue</h2>
              <p className="mt-1 text-sm text-slate-400">Payment data and recovery workflows will appear here in a later stage.</p>
            </div>
            <span className="rounded-md bg-slate-800 px-2.5 py-1 text-xs font-medium text-slate-300">Planned</span>
          </div>
          <div className="mt-6 rounded-xl border border-dashed border-slate-700 p-8 text-center text-sm text-slate-500">No transactions loaded</div>
        </section>
      </div>
    </main>
  );
}
