import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * Surfaces. Flat by default: elevation is used for genuinely interactive or
 * overlay content, not for every block on the page.
 */

export function Card({
  className,
  tone = "surface",
  ...props
}: React.HTMLAttributes<HTMLDivElement> & {
  tone?: "surface" | "mint" | "muted" | "outline" | "sunken";
}) {
  const tones = {
    surface: "bg-surface border border-line shadow-soft",
    mint: "bg-surface-mint border border-brand-soft/70",
    muted: "bg-surface-muted border border-line-soft",
    outline: "bg-transparent border border-line",
    sunken: "bg-surface-sunken border border-line-soft",
  } as const;
  return (
    <div
      className={cn("rounded-card", tones[tone], className)}
      {...props}
    />
  );
}

export function CardHeader({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("flex flex-col gap-1 p-5 sm:p-6", className)} {...props} />;
}

export function CardTitle({
  className,
  as: Tag = "h3",
  ...props
}: React.HTMLAttributes<HTMLHeadingElement> & { as?: "h2" | "h3" | "h4" }) {
  return <Tag className={cn("text-h3", className)} {...props} />;
}

export function CardDescription({
  className,
  ...props
}: React.HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn("text-small text-ink-muted", className)} {...props} />;
}

export function CardContent({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("px-5 pb-5 sm:px-6 sm:pb-6", className)} {...props} />;
}

export function CardFooter({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-3 border-t border-line-soft px-5 py-4 sm:px-6",
        className,
      )}
      {...props}
    />
  );
}

/** A compact labelled figure used across the dashboard and stat rows. */
export function Stat({
  label,
  value,
  hint,
  tone = "neutral",
  icon,
  className,
}: {
  label: string;
  value: React.ReactNode;
  hint?: React.ReactNode;
  tone?: "neutral" | "brand" | "success" | "warning" | "danger";
  icon?: React.ReactNode;
  className?: string;
}) {
  const tones = {
    neutral: "text-ink",
    brand: "text-brand",
    success: "text-success",
    warning: "text-warning",
    danger: "text-danger",
  } as const;
  return (
    <div className={cn("flex flex-col gap-1", className)}>
      <span className="flex items-center gap-1.5 text-caption font-semibold uppercase tracking-[0.08em] text-ink-faint">
        {icon}
        {label}
      </span>
      <span className={cn("font-display text-h2 tabular-nums", tones[tone])}>{value}</span>
      {hint ? <span className="text-small text-ink-muted">{hint}</span> : null}
    </div>
  );
}
