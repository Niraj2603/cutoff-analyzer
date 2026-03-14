function formatFileSize(bytes) {
  if (!bytes) {
    return "0 KB";
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export default function UploadSection({
  file,
  dragActive,
  disabled,
  error,
  onBrowse,
  onDrop,
  onDragStateChange,
  onConvert,
}) {
  return (
    <section className="animate-rise rounded-[28px] border border-white/70 bg-white/80 p-6 shadow-panel backdrop-blur">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.24em] text-coral">Step 1</p>
          <h2 className="mt-2 font-display text-3xl font-bold text-ink">Upload CAP Round PDF</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate">
            Drag and drop the official MHT-CET cutoff PDF here. The converter extracts college,
            branch, and category cutoffs into a counseling-ready Excel workbook.
          </p>
        </div>
        <div className="rounded-full border border-gold/70 bg-gold/20 px-4 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-ink">
          Supports CAP Round I, II, and III
        </div>
      </div>

      <label
        className={[
          "flex min-h-[300px] cursor-pointer flex-col items-center justify-center rounded-[24px] border-2 border-dashed px-6 py-10 text-center transition",
          dragActive
            ? "border-pine bg-pine/10"
            : "border-slate/30 bg-gradient-to-br from-mist to-white hover:border-coral/60 hover:bg-coral/5",
          disabled ? "cursor-not-allowed opacity-70" : "",
        ].join(" ")}
        onDragEnter={() => onDragStateChange(true)}
        onDragOver={(event) => {
          event.preventDefault();
          onDragStateChange(true);
        }}
        onDragLeave={() => onDragStateChange(false)}
        onDrop={onDrop}
      >
        <input
          type="file"
          accept=".pdf"
          className="hidden"
          onChange={onBrowse}
          disabled={disabled}
        />
        <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-full bg-ink text-4xl text-white">
          PDF
        </div>
        <h3 className="font-display text-2xl font-bold text-ink">
          Drag &amp; Drop CAP Round PDF here or click to browse
        </h3>
        <p className="mt-3 max-w-xl text-sm leading-6 text-slate">
          Accepted format: <span className="font-semibold text-ink">.pdf</span> only. Large annual
          cutoff files are supported and processed in the background.
        </p>

        {file ? (
          <div className="mt-8 rounded-2xl border border-pine/30 bg-pine/10 px-5 py-4 text-left">
            <p className="text-sm font-semibold text-pine">File selected successfully</p>
            <p className="mt-1 text-base font-bold text-ink">{file.name}</p>
            <p className="mt-1 text-sm text-slate">{formatFileSize(file.size)}</p>
          </div>
        ) : null}
      </label>

      <div className="mt-6 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <p className="text-sm text-slate">
          The Excel is formatted for fast filtering by city, district, branch, category, and college
          type during counseling.
        </p>
        <button
          type="button"
          className="rounded-full bg-ink px-6 py-3 font-semibold text-white transition hover:bg-pine disabled:cursor-not-allowed disabled:bg-slate/40"
          onClick={onConvert}
          disabled={!file || disabled}
        >
          Convert to Excel
        </button>
      </div>

      {error ? (
        <div className="mt-5 rounded-2xl border border-coral/40 bg-coral/10 px-4 py-3 text-sm text-ink">
          {error}
        </div>
      ) : null}
    </section>
  );
}
