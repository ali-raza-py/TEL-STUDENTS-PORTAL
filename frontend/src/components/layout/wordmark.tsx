import Link from "next/link";

/**
 * The TEL wordmark.
 *
 * A monogram built from the three initials plus a soft mint tile, followed by
 * the full name in the display face. No separate logo asset to keep in sync,
 * and it stays legible from 28px to 180px wide.
 */
export function TelWordmark({
  size = "md",
  className = "",
  showSubtitle = true,
}: {
  size?: "sm" | "md" | "lg";
  className?: string;
  showSubtitle?: boolean;
}) {
  const tile = {
    sm: "h-7 w-7 text-[0.625rem]",
    md: "h-9 w-9 text-xs",
    lg: "h-12 w-12 text-sm",
  }[size];
  const title = {
    sm: "text-body",
    md: "text-body-lg",
    lg: "text-h2",
  }[size];
  const subtitle = size === "sm" ? "hidden" : "block";

  return (
    <Link
      href="/dashboard"
      className={`group inline-flex items-center gap-3 rounded-control ${className}`}
      aria-label="TEL Education Link — go to dashboard"
    >
      <span
        className={`relative flex ${tile} shrink-0 items-center justify-center rounded-[0.7rem] bg-brand font-display font-semibold tracking-tight text-white shadow-hairline`}
      >
        TEL
        <span
          aria-hidden
          className="absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border-2 border-canvas bg-subject-mint"
        />
      </span>
      <span className="flex min-w-0 flex-col leading-tight">
        <span className={`font-display font-semibold tracking-tight text-ink ${title}`}>
          TEL Education Link
        </span>
        {showSubtitle ? (
          <span className={`${subtitle} text-label font-semibold uppercase text-ink-faint`}>
            Student Portal
          </span>
        ) : null}
      </span>
    </Link>
  );
}
