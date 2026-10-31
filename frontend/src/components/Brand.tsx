/** The logo: a person inside a rounded square, in the accent color. */
export function BrandMark({ size = 30 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="9" className="fill-accent" />
      <circle cx="16" cy="12" r="5" className="fill-on-accent" />
      <path d="M7 26c1.5-5 5-7 9-7s7.5 2 9 7" fill="none" strokeWidth="2.5" strokeLinecap="round" className="stroke-on-accent" />
    </svg>
  );
}

/** A round letter badge for people who have no photo. The color comes from the name, so it stays the same. */
export function Avatar({ name, size = 44 }: { name: string; size?: number }) {
  const hues = [250, 280, 200, 160, 20, 330];
  const hue = hues[[...name].reduce((sum, ch) => sum + ch.charCodeAt(0), 0) % hues.length];
  return (
    <span
      className="flex shrink-0 items-center justify-center rounded-full font-bold text-white"
      style={{ width: size, height: size, fontSize: size * 0.4, background: `linear-gradient(135deg, hsl(${hue} 70% 55%), hsl(${(hue + 40) % 360} 70% 45%))` }}
      aria-hidden="true"
    >
      {name.trim().charAt(0).toUpperCase() || "?"}
    </span>
  );
}
