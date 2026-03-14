export default function DownloadSection({ status, apiBase, onReset }) {
  const downloadUrl = status?.job_id ? `${apiBase}/api/download/${status.job_id}` : null;
  const isError = status?.status === "error";

  return (
    <section className="animate-rise rounded-[28px] border border-white/70 bg-white/90 p-6 shadow-panel backdrop-blur">
      <div
        className={[
          "rounded-[24px] p-6",
          isError ? "bg-coral/12 text-ink" : "bg-pine/12 text-ink",
        ].join(" ")}
      >
        <p className="text-sm font-semibold uppercase tracking-[0.24em] text-coral">Step 3</p>
        <h2 className="mt-2 font-display text-3xl font-bold">
          {isError ? "Processing Stopped" : "Conversion Complete!"}
        </h2>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-slate">
          {isError
            ? status.error || "The PDF parser stopped before completing the workbook."
            : "The workbook is ready for counselor use with filters, cutoff columns, and guidance sheet."}
        </p>

        <div className="mt-6 grid gap-4 md:grid-cols-3">
          <div className="rounded-2xl bg-white/80 p-4">
            <p className="text-xs uppercase tracking-[0.18em] text-slate">Colleges parsed</p>
            <p className="mt-2 text-3xl font-bold">{status.colleges_found || 0}</p>
          </div>
          <div className="rounded-2xl bg-white/80 p-4">
            <p className="text-xs uppercase tracking-[0.18em] text-slate">Branches parsed</p>
            <p className="mt-2 text-3xl font-bold">{status.branches_found || 0}</p>
          </div>
          <div className="rounded-2xl bg-white/80 p-4">
            <p className="text-xs uppercase tracking-[0.18em] text-slate">Total rows</p>
            <p className="mt-2 text-3xl font-bold">{status.rows_found || 0}</p>
          </div>
        </div>
      </div>

      <div className="mt-6 flex flex-col gap-4 md:flex-row md:items-center">
        {downloadUrl ? (
          <a
            href={downloadUrl}
            className="inline-flex items-center justify-center rounded-full bg-ink px-6 py-3 font-semibold text-white transition hover:bg-pine"
          >
            {isError && status.partial_available ? "Download Partial File" : "Download Excel File"}
          </a>
        ) : null}
        <button
          type="button"
          className="inline-flex items-center justify-center rounded-full border border-ink/20 bg-white px-6 py-3 font-semibold text-ink transition hover:border-coral hover:text-coral"
          onClick={onReset}
        >
          Convert Another PDF
        </button>
      </div>

      {status.output_filename ? (
        <p className="mt-4 text-sm text-slate">
          Generated file: <span className="font-semibold text-ink">{status.output_filename}</span>
        </p>
      ) : null}
    </section>
  );
}
