import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * Data table.
 *
 * Used for genuinely tabular data (attendance register, result sheet, audit
 * trail). Everything else in the portal uses cards, because a card grid reads
 * better than a table for narrative academic content.
 */

export function DataTable({ className, ...props }: React.TableHTMLAttributes<HTMLTableElement>) {
  return (
    <div className="overflow-x-auto rounded-card border border-line bg-surface">
      <table className={cn("w-full min-w-[40rem] border-collapse text-left", className)} {...props} />
    </div>
  );
}

export function THead({ className, ...props }: React.HTMLAttributes<HTMLTableSectionElement>) {
  return <thead className={cn("border-b border-line bg-surface-muted/70", className)} {...props} />;
}

export function TBody({ className, ...props }: React.HTMLAttributes<HTMLTableSectionElement>) {
  return <tbody className={cn("divide-y divide-line-soft", className)} {...props} />;
}

export function TR({ className, ...props }: React.HTMLAttributes<HTMLTableRowElement>) {
  return <tr className={cn("transition-colors duration-150 hover:bg-surface-muted/50", className)} {...props} />;
}

export function TH({
  className,
  scope = "col",
  ...props
}: React.ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th
      scope={scope}
      className={cn(
        "whitespace-nowrap px-4 py-3 text-label font-bold uppercase text-ink-faint",
        className,
      )}
      {...props}
    />
  );
}

export function TD({
  className,
  ...props
}: React.TdHTMLAttributes<HTMLTableCellElement>) {
  return <td className={cn("px-4 py-3.5 align-middle text-small text-ink", className)} {...props} />;
}

/** Visually hidden header for a table that reads better with row labels. */
export function RowHeader({ className, ...props }: React.ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th
      scope="row"
      className={cn("px-4 py-3.5 text-left text-small font-medium text-ink", className)}
      {...props}
    />
  );
}
