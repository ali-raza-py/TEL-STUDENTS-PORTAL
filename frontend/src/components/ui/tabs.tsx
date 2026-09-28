"use client";

import * as TabsPrimitive from "@radix-ui/react-tabs";
import { ChevronLeft, ChevronRight } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";
import { Button } from "./button";

export const Tabs = TabsPrimitive.Root;

export function TabsList({
  className,
  children,
  ...props
}: React.ComponentPropsWithoutRef<typeof TabsPrimitive.List>) {
  return (
    <TabsPrimitive.List
      className={cn(
        "no-scrollbar flex gap-1 overflow-x-auto rounded-pill border border-line bg-surface-muted p-1",
        className,
      )}
      {...props}
    >
      {children}
    </TabsPrimitive.List>
  );
}

export function TabsTrigger({
  className,
  ...props
}: React.ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      className={cn(
        "whitespace-nowrap rounded-pill px-4 py-2 text-small font-semibold text-ink-muted transition-colors duration-200",
        "hover:text-ink data-[state=active]:bg-surface data-[state=active]:text-brand-deep data-[state=active]:shadow-[var(--shadow-hairline)]",
        className,
      )}
      {...props}
    />
  );
}

export const TabsContent = TabsPrimitive.Content;

export interface PaginationProps {
  page: number;
  numPages: number;
  hasNext: boolean;
  hasPrevious: boolean;
  onChange: (page: number) => void;
  className?: string;
  label?: string;
}

export function Pagination({
  page,
  numPages,
  hasNext,
  hasPrevious,
  onChange,
  className,
  label = "Pagination",
}: PaginationProps) {
  if (numPages <= 1) return null;
  return (
    <nav
      aria-label={label}
      className={cn("flex items-center justify-between gap-3 pt-5", className)}
    >
      <p className="text-small text-ink-muted">
        Page <span className="font-medium text-ink">{page}</span> of {numPages}
      </p>
      <div className="flex items-center gap-2">
        <Button
          variant="secondary"
          size="sm"
          disabled={!hasPrevious}
          onClick={() => onChange(page - 1)}
          icon={<ChevronLeft className="h-4 w-4" />}
        >
          Previous
        </Button>
        <Button
          variant="secondary"
          size="sm"
          disabled={!hasNext}
          onClick={() => onChange(page + 1)}
        >
          Next
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
    </nav>
  );
}
