// Shared class names so every button and card looks the same.
// 44px minimum height on buttons/inputs = comfortable tap target on phones.

export const btnPrimary =
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-full bg-fg px-5 text-sm font-semibold text-bg transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-60";

export const btnSecondary =
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-full border border-line bg-surface-2 px-5 text-sm font-medium text-fg transition hover:border-muted/50 disabled:cursor-not-allowed disabled:opacity-60";

export const card = "rounded-[var(--radius-card)] border border-line bg-surface";

export const input =
  "block min-h-11 w-full rounded-xl border border-line bg-surface-2 px-4 text-base text-fg placeholder:text-muted/70 focus:border-accent focus:outline-none";

export const label = "mb-2 block text-sm font-medium text-fg";
