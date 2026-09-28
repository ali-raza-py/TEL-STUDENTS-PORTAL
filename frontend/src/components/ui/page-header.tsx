import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * Page chrome. Every route renders the same header shape: title, one line of
 * context, then actions — so the portal reads as one product.
 */

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
  className,
}: {
  eyebrow?: React.ReactNode;
  title: React.ReactNode;
  description?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
}) {
  return (
    <header
      className={cn(
        "flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between",
        className,
      )}
    >
      <div className="min-w-0">
        {eyebrow ? (
          <p className="mb-1.5 text-label font-bold uppercase text-ink-faint">
            {eyebrow}
          </p>
        ) : null}
        <h1 className="font-display text-h1 font-extrabold tracking-[-0.026em] text-ink">{title}</h1>
        {description ? (
          <p className="mt-2 max-w-2xl text-body text-ink-muted">{description}</p>
        ) : null}
      </div>
      {actions ? (
        <div className="flex shrink-0 flex-wrap items-center gap-2.5">{actions}</div>
      ) : null}
    </header>
  );
}

/** Section heading used inside long pages. */
export function SectionHeading({
  title,
  description,
  actions,
  className,
  as = "h2",
}: {
  title: React.ReactNode;
  description?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
  as?: "h2" | "h3";
}) {
  const Tag = as;
  return (
    <div className={cn("flex flex-wrap items-end justify-between gap-3", className)}>
      <div className="min-w-0">
        <Tag className="font-display text-h2 font-bold tracking-[-0.02em] text-ink">{title}</Tag>
        {description ? <p className="mt-1 text-small text-ink-muted">{description}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  );
}

/** Consistent vertical rhythm between page sections. */
export function PageStack({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <div className={cn("flex flex-col gap-6 sm:gap-7", className)}>{children}</div>;
}
