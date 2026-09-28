"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * Floating background.
 *
 * Soft, low-opacity educational glyphs drifting across the viewport. The
 * opacity is deliberately low — these are atmosphere, not content — and they
 * never intercept pointer events so they cannot break interaction.
 */
const FLOATING_ELEMENTS = [
  { icon: "graduation", top: "5%", left: "3%", delay: "0s", size: 48 },
  { icon: "book", top: "15%", right: "5%", delay: "2s", size: 40 },
  { icon: "award", top: "30%", left: "2%", delay: "4s", size: 36 },
  { icon: "target", bottom: "20%", right: "3%", delay: "1s", size: 44 },
  { icon: "lightbulb", bottom: "10%", left: "5%", delay: "3s", size: 42 },
  { icon: "globe", top: "50%", left: "50%", delay: "5s", size: 38 },
];

export function FloatingEducationBackground({
  className,
  opacity = 0.05,
}: {
  className?: string;
  opacity?: number;
}) {
  return (
    <div
      className={cn(
        "pointer-events-none fixed inset-0 overflow-hidden z-0",
        className,
      )}
      aria-hidden="true"
    >
      {FLOATING_ELEMENTS.map((el, i) => (
        <div
          key={i}
          className="absolute rounded-2xl bg-brand-tint animate-float"
          style={{
            opacity,
            animationDelay: el.delay,
            width: el.size,
            height: el.size,
            top: el.top,
            right: el.right,
            bottom: el.bottom,
            left: el.left,
          }}
        >
          <span className="block h-full w-full rounded-2xl bg-brand-tint" />
        </div>
      ))}
    </div>
  );
}

export function FloatingOrbs({
  className,
  count = 5,
  color = "brand",
  opacity = 0.04,
}: {
  className?: string;
  count?: number;
  color?: "brand" | "success" | "warning" | "danger" | "info" | "lilac" | "mint";
  opacity?: number;
}) {
  const colorClasses = {
    brand: "bg-brand-tint",
    success: "bg-success-soft",
    warning: "bg-warning-soft",
    danger: "bg-danger-soft",
    info: "bg-info-soft",
    lilac: "bg-subject-lilac-soft",
    mint: "bg-subject-mint-soft",
  };

  return (
    <div
      className={cn("pointer-events-none absolute inset-0 overflow-hidden z-0", className)}
      aria-hidden="true"
    >
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className={cn("absolute rounded-full animate-blob", colorClasses[color])}
          style={{
            opacity,
            width: 40 + (i * 50) % 160,
            height: 40 + (i * 50) % 160,
            top: `${(i * 19) % 75}%`,
            left: `${(i * 27) % 75}%`,
            animationDelay: `${i * 2}s`,
            animationDuration: `${20 + i * 5}s`,
          }}
        />
      ))}
    </div>
  );
}

/**
 * Page entrance.
 *
 * Opacity only — deliberately no `translateY`. A lingering transform from a
 * `both`-filled animation would become the containing block for any
 * `position: fixed` descendant, which silently breaks drawers and modals.
 */
export function PageTransitionWrapper({
  children,
  className,
  delay = 0,
}: {
  children: React.ReactNode;
  className?: string;
  delay?: number;
}) {
  return (
    <div
      className={cn("animate-fade-in", className)}
      style={delay > 0 ? { animationDelay: `${delay}s` } : undefined}
    >
      {children}
    </div>
  );
}

export function EducationalCard({
  children,
  icon,
  iconColor = "brand",
  className,
  variant = "default",
  hover = true,
}: {
  children: React.ReactNode;
  icon?: React.ReactNode;
  iconColor?: "brand" | "success" | "warning" | "danger" | "info" | "lilac" | "mint";
  className?: string;
  variant?: "default" | "elevated" | "glass" | "3d";
  hover?: boolean;
}) {
  const variants = {
    default: cn(
      "bg-surface border border-line shadow-[var(--shadow-hairline)]",
      hover && "transition-shadow hover:shadow-[var(--shadow-soft)]",
    ),
    elevated: cn(
      "bg-surface border border-line shadow-[var(--shadow-hairline)]",
      hover && "transition-shadow hover:shadow-[var(--shadow-raised)]",
    ),
    glass: "bg-surface border border-line shadow-[var(--shadow-hairline)]",
    "3d": "bg-surface border border-line shadow-[var(--shadow-soft)]",
  };

  /* The icon renders as a plain glyph in a brand tint — no pastel square
     behind it. Large colourful tiles read as decoration; a single tinted
     glyph reads as a label. */
  const iconColors = {
    brand: "text-brand",
    success: "text-success",
    warning: "text-warning",
    danger: "text-danger",
    info: "text-info",
    lilac: "text-subject-lilac",
    mint: "text-subject-mint",
  };

  return (
    <div
      className={cn(
        "rounded-card p-5 sm:p-6",
        variants[variant],
        className,
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">{children}</div>
        {icon ? (
          <span aria-hidden className={cn("shrink-0", iconColors[iconColor])}>
            {icon}
          </span>
        ) : null}
      </div>
    </div>
  );
}

export function StatCard({
  label,
  value,
  trend,
  trendUp = true,
  icon,
  iconColor = "brand",
  className,
  hint,
}: {
  label: string;
  value: React.ReactNode;
  trend?: string;
  trendUp?: boolean;
  icon?: React.ReactNode;
  iconColor?: "brand" | "success" | "warning" | "danger" | "info" | "lilac" | "mint";
  className?: string;
  hint?: string;
}) {
  const iconColors = {
    brand: "text-brand",
    success: "text-success",
    warning: "text-warning",
    danger: "text-danger",
    info: "text-info",
    lilac: "text-subject-lilac",
    mint: "text-subject-mint",
  };

  return (
    <div className={cn("h-full", className)}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-label font-bold uppercase text-ink-faint">{label}</p>
          {/* Tabular, tight, heavy — the figure is the point of the card. */}
          <p className="mt-2 font-display text-metric font-extrabold tabular-nums text-ink">
            {value}
          </p>
          {hint && <p className="mt-1.5 text-small text-ink-muted">{hint}</p>}
        </div>
        {/* Rendered as-is: a progress ring shows through, a glyph stays a
            glyph. No pastel container is drawn around it. */}
        {icon ? (
          <span aria-hidden className={cn("shrink-0", iconColors[iconColor])}>
            {icon}
          </span>
        ) : null}
      </div>
      {trend && (
        <div
          className={cn(
            "mt-4 flex items-center gap-1.5 text-small font-semibold",
            trendUp ? "text-success" : "text-danger",
          )}
        >
          <span>{trend}</span>
        </div>
      )}
    </div>
  );
}

export function SubjectPill({
  children,
  color = "sage",
  size = "md",
  className,
}: {
  children: React.ReactNode;
  color?: "sage" | "mint" | "sky" | "sand" | "clay" | "lilac";
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const colors = {
    sage: "bg-subject-sage-soft text-subject-sage border-subject-sage/30",
    mint: "bg-subject-mint-soft text-subject-mint border-subject-mint/30",
    sky: "bg-subject-sky-soft text-subject-sky border-subject-sky/30",
    sand: "bg-subject-sand-soft text-subject-sand border-subject-sand/30",
    clay: "bg-subject-clay-soft text-subject-clay border-subject-clay/30",
    lilac: "bg-subject-lilac-soft text-subject-lilac border-subject-lilac/30",
  };

  const sizes = {
    sm: "px-2.5 py-0.5 text-xs",
    md: "px-3 py-1 text-sm",
    lg: "px-4 py-1.5 text-base",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border font-medium",
        "transition-colors duration-200",
        colors[color],
        sizes[size],
        className,
      )}
    >
      {children}
    </span>
  );
}

export function ProgressRingAnimated({
  value,
  size = 80,
  strokeWidth = 8,
  color = "brand",
  className,
  children,
}: {
  value: number | null;
  size?: number;
  strokeWidth?: number;
  color?: "brand" | "success" | "warning" | "danger";
  className?: string;
  children?: React.ReactNode;
}) {
  const colors = {
    brand: "stroke-brand",
    success: "stroke-success",
    warning: "stroke-warning",
    danger: "stroke-danger",
  };

  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const clamped = value === null ? 0 : Math.max(0, Math.min(100, value));
  const offset = circumference - (clamped / 100) * circumference;

  return (
    <div
      className={cn("relative inline-flex items-center justify-center", className)}
      style={{ width: size, height: size }}
      role="img"
      aria-label={value === null ? "No data" : `${Math.round(clamped)} percent`}
    >
      <svg width={size} height={size} className="-rotate-90" aria-hidden>
        <defs>
          <linearGradient id={`grad-${color}`} x1="0%" y1="0%" x2="100%" y2="0%">
            {/* stop-color accepts custom properties, so the ring follows the
                brand token instead of a hardcoded hex drifting from it. */}
            <stop offset="0%" stopColor="var(--color-brand)" stopOpacity="0.55" />
            <stop offset="100%" stopColor="var(--color-brand)" stopOpacity="1" />
          </linearGradient>
        </defs>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={strokeWidth}
          className="stroke-surface-sunken"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className={cn(
            "transition-all duration-1000 ease-out",
            colors[color],
          )}
          style={{
            strokeDashoffset: offset,
            stroke:
              color === "brand"
                ? "url(#grad-brand)"
                : undefined,
          }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        {children ?? (
          <span className="font-display text-2xl tabular-nums text-ink">
            {value === null ? "—" : `${Math.round(clamped)}%`}
          </span>
        )}
      </div>
    </div>
  );
}
