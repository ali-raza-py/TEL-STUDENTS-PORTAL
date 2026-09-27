import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * Progress indicators. Always paired with a text value so the bar is never the
 * only way the number is communicated.
 */

export function Progress({
  value,
  className,
  tone = "brand",
  label,
  size = "md",
}: {
  /** 0–100. `null` renders the track in its empty state. */
  value: number | null;
  className?: string;
  tone?: "brand" | "success" | "warning" | "danger" | "muted";
  label?: string;
  size?: "sm" | "md" | "lg";
}) {
  const clamped = value === null ? null : Math.max(0, Math.min(100, value));
  const tones = {
    brand: "bg-brand",
    success: "bg-success",
    warning: "bg-warning",
    danger: "bg-danger",
    muted: "bg-line-strong",
  } as const;
  const heights = { sm: "h-1.5", md: "h-2", lg: "h-2.5" } as const;

  return (
    <div
      role="progressbar"
      aria-valuenow={clamped ?? undefined}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={label}
      className={cn("w-full overflow-hidden rounded-pill bg-surface-sunken", heights[size], className)}
    >
      {clamped !== null ? (
        <div
          className={cn("meter h-full rounded-pill animate-progress", tones[tone])}
          style={{ width: `${clamped}%` }}
        />
      ) : null}
    </div>
  );
}

/** Horizontal bar used in the subject performance list. */
export function BarRow({
  label,
  value,
  caption,
  barClassName,
  className,
  trailing,
}: {
  label: React.ReactNode;
  value: React.ReactNode;
  caption?: React.ReactNode;
  barClassName?: string;
  className?: string;
  trailing?: React.ReactNode;
}) {
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <div className="flex items-baseline justify-between gap-3">
        <span className="min-w-0 truncate text-body text-ink">{label}</span>
        <span className="shrink-0 font-display text-body font-semibold tabular-nums text-ink">
          {value}
        </span>
      </div>
      <Progress value={typeof value === "number" ? value : null} tone="muted" className={barClassName} label={typeof label === "string" ? label : undefined} size="sm" />
      {caption || trailing ? (
        <div className="flex items-center justify-between gap-3 text-caption text-ink-faint">
          <span className="truncate">{caption}</span>
          {trailing}
        </div>
      ) : null}
    </div>
  );
}

/** Compact ring for headline figures. */
export function ProgressRing({
  value,
  size = 84,
  strokeWidth = 8,
  tone = "brand",
  children,
  label,
}: {
  value: number | null;
  size?: number;
  strokeWidth?: number;
  tone?: "brand" | "success" | "warning" | "danger";
  children?: React.ReactNode;
  label?: string;
}) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const clamped = value === null ? 0 : Math.max(0, Math.min(100, value));
  const tones = {
    brand: "stroke-brand",
    success: "stroke-success",
    warning: "stroke-warning",
    danger: "stroke-danger",
  } as const;

  return (
    <div
      className="relative inline-flex items-center justify-center"
      style={{ width: size, height: size }}
      role="img"
      aria-label={label ?? (value === null ? "No data" : `${Math.round(clamped)} percent`)}
    >
      <svg width={size} height={size} className="-rotate-90" aria-hidden>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={strokeWidth}
          className="stroke-surface-sunken"
        />
        {value !== null ? (
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={circumference - (clamped / 100) * circumference}
            className={cn("transition-[stroke-dashoffset] duration-700", tones[tone])}
          />
        ) : null}
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        {children ?? (
          <span className="font-display text-h2 tabular-nums text-ink">
            {value === null ? "—" : `${Math.round(clamped)}%`}
          </span>
        )}
      </div>
    </div>
  );
}
