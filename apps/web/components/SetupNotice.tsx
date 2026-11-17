// Shown when the Supabase keys haven't been added to .env yet.
export function SetupNotice() {
  return (
    <div role="status" className="rounded-2xl border border-accent/40 bg-accent/10 p-4 text-sm leading-relaxed text-fg">
      <p className="font-semibold">Almost ready: connect Supabase</p>
      <p className="mt-1 text-fg/85">
        Copy <code className="rounded bg-black/40 px-1">.env.example</code> to{" "}
        <code className="rounded bg-black/40 px-1">.env</code>, paste your Supabase URL and
        publishable key, then restart the app. Full steps are in the README.
      </p>
    </div>
  );
}
