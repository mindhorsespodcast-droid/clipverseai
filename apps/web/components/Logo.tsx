// The "Slice" mark: a wide 16:9 frame with a tall 9:16 clip cut through it.
type MarkProps = { size?: number; className?: string };

export function LogoMark({ size = 28, className }: MarkProps) {
  return (
    <svg
      width={size}
      height={(size * 32) / 44}
      viewBox="0 0 44 32"
      fill="none"
      aria-hidden="true"
      className={className}
    >
      <defs>
        <mask id="cv-slice-gap">
          <rect width="44" height="32" fill="white" />
          <rect x="15" y="0" width="14" height="32" fill="black" />
        </mask>
      </defs>
      <rect
        x="3"
        y="6"
        width="38"
        height="20"
        rx="6.5"
        stroke="currentColor"
        strokeWidth="3.5"
        mask="url(#cv-slice-gap)"
      />
      <rect x="17.5" y="1" width="9" height="30" rx="3" fill="#FF6B3D" />
    </svg>
  );
}

export function Logo({ size = 28 }: { size?: number }) {
  return (
    <span className="inline-flex items-center gap-2.5 text-fg">
      <LogoMark size={size} />
      <span
        className="font-display font-semibold tracking-[-0.04em]"
        style={{ fontSize: size * 0.68 }}
      >
        ClipVerse <span className="text-muted">AI</span>
      </span>
    </span>
  );
}
