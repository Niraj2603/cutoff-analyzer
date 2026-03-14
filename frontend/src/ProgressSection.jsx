function formatEta(seconds) {
  if (seconds === null || seconds === undefined) {
    return "Calculating...";
  }
  if (seconds < 60) {
    return `${seconds}s`;
  }
  const minutes = Math.floor(seconds / 60);
  const remaining = seconds % 60;
  return `${minutes}m ${remaining}s`;
}

export default function ProgressSection({ status }) {
  return (
    <section className="animate-rise rounded-[28px] border border-white/70 bg-white/85 p-6 shadow-panel backdrop-blur">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.24em] text-coral">Step 2</p>
          <h2 className="mt-2 font-display text-3xl font-bold text-ink">Processing PDF</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate">
            The backend is reading pages, matching cutoffs to categories, and assembling a
            counselor-friendly Excel workbook.
          </p>
        </div>
        <div className="rounded-3xl bg-ink px-5 py-4 text-white">
          <p className="text-xs uppercase tracking-[0.18em] text-white/70">Estimated time left</p>
          <p className="mt-2 text-2xl font-bold">{formatEta(status.estimated_time_remaining_seconds)}</p>
        </div>
      </div>

      <div className="mt-8 overflow-hidden rounded-full bg-mist">
        <div
          className="h-5 rounded-full bg-gradient-to-r from-coral via-gold to-pine transition-all duration-700 ease-out animate-pulsebar"
          style={{ width: `${Math.max(status.progress_pct || 4, 4)}%` }}
        />
      </div>

      <div className="mt-4 flex items-center justify-between text-sm text-slate">
        <span>{status.message || "Reading PDF pages..."}</span>
        <span className="font-semibold text-ink">{status.progress_pct || 0}%</span>
      </div>

      <div className="mt-8 grid gap-4 md:grid-cols-3">
        <div className="rounded-3xl bg-mist p-5">
          <p className="text-xs uppercase tracking-[0.18em] text-slate">Colleges parsed</p>
          <p className="mt-2 text-3xl font-bold text-ink">{status.colleges_found || 0}</p>
        </div>
        <div className="rounded-3xl bg-mist p-5">
          <p className="text-xs uppercase tracking-[0.18em] text-slate">Branches parsed</p>
          <p className="mt-2 text-3xl font-bold text-ink">{status.branches_found || 0}</p>
        </div>
        <div className="rounded-3xl bg-mist p-5">
          <p className="text-xs uppercase tracking-[0.18em] text-slate">Current target</p>
          <p className="mt-2 text-base font-semibold text-ink">
            {status.current_college || status.current_branch || "Reading PDF layout..."}
          </p>
        </div>
      </div>
    </section>
  );
}
