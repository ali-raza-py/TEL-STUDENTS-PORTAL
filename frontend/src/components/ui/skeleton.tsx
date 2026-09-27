import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * Loading placeholders. These mirror the shape of the content they replace so
 * the page does not jump when data arrives.
 */

function bar(className: string) {
  return <div className={cn("animate-shimmer rounded-md bg-surface-sunken", className)} />;
}

export function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div aria-hidden className={cn("animate-shimmer rounded-md bg-surface-sunken", className)} {...props} />;
}

export function SkeletonText({
  lines = 3,
  className,
}: {
  lines?: number;
  className?: string;
}) {
  return (
    <div className={cn("space-y-2", className)} aria-hidden>
      {Array.from({ length: lines }).map((_, index) => (
        <div
          key={index}
          className={cn(
            "animate-shimmer rounded-md bg-surface-sunken",
            index === lines - 1 ? "w-2/3" : "w-full",
          )}
          style={{ height: index === 0 ? 18 : 12 }}
        />
      ))}
    </div>
  );
}

export function SkeletonCard({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={cn("rounded-card border border-line bg-surface p-5 shadow-soft", className)}
    >
      {bar("h-3 w-24")}
      <div className="mt-4 space-y-2">
        {bar("h-6 w-2/3")}
        {bar("h-3 w-1/2")}
      </div>
    </div>
  );
}

export function SkeletonStats({ count = 3 }: { count?: number }) {
  return (
    <div className="grid gap-3 sm:grid-cols-3" aria-hidden>
      {Array.from({ length: count }).map((_, index) => (
        <div key={index} className="rounded-card border border-line bg-surface p-5 shadow-soft">
          {bar("h-3 w-20")}
          {bar("mt-4 h-7 w-24")}
          {bar("mt-3 h-3 w-16")}
        </div>
      ))}
    </div>
  );
}

export function SkeletonList({ rows = 4, className }: { rows?: number; className?: string }) {
  return (
    <div className={cn("space-y-2", className)} aria-hidden>
      {Array.from({ length: rows }).map((_, index) => (
        <div
          key={index}
          className="flex items-center gap-4 rounded-control border border-line bg-surface px-4 py-3.5"
        >
          {bar("h-9 w-9 rounded-pill")}
          <div className="flex-1 space-y-2">
            {bar("h-3.5 w-1/2")}
            {bar("h-3 w-1/3")}
          </div>
        </div>
      ))}
    </div>
  );
}

export function SkeletonPage({ variant = "cards" }: { variant?: "cards" | "list" | "rows" }) {
  if (variant === "list") return <SkeletonList rows={6} />;
  if (variant === "rows") {
    return (
      <div className="space-y-2" aria-hidden>
        {Array.from({ length: 7 }).map((_, index) => (
          <div key={index} className="rounded-card border border-line bg-surface p-4 shadow-hairline">
            {bar("h-3.5 w-1/3")}
            {bar("mt-3 h-3 w-2/3")}
          </div>
        ))}
      </div>
    );
  }
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3" aria-hidden>
      {Array.from({ length: 6 }).map((_, index) => (
        <SkeletonCard key={index} />
      ))}
    </div>
  );
}

/** Screen-reader announcement paired with a visible spinner. */
export function LoadingBlock({ label = "Loading" }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="flex items-center justify-center gap-3 py-12">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-brand-soft border-t-brand" />
      <span className="text-small text-ink-muted">{label}…</span>
    </div>
  );
}
