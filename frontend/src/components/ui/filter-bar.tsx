"use client";

import { Search, X } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";
import { Button } from "./button";
import { Input, Select } from "./input";

/**
 * Search and filter controls.
 *
 * Every filter here changes the API query — there are no client-side
 * "decorative" filters that only hide already-loaded rows.
 */

export function SearchInput({
  value,
  onChange,
  placeholder = "Search",
  className,
  label,
  autoFocus,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
  label?: string;
  autoFocus?: boolean;
}) {
  return (
    <div className={cn("relative min-w-0", className)}>
      <label className="sr-only" htmlFor="tel-search">
        {label ?? placeholder}
      </label>
      <Search
        className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-faint"
        aria-hidden
      />
      <Input
        id="tel-search"
        type="search"
        value={value}
        autoFocus={autoFocus}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="pl-9 pr-9"
      />
      {value ? (
        <button
          type="button"
          onClick={() => onChange("")}
          aria-label="Clear search"
          className="absolute right-2.5 top-1/2 -translate-y-1/2 rounded p-1 text-ink-faint transition-colors hover:bg-surface-muted hover:text-ink"
        >
          <X className="h-3.5 w-3.5" aria-hidden />
        </button>
      ) : null}
    </div>
  );
}

export interface FilterOption {
  value: string;
  label: string;
  count?: number;
}

export function FilterSelect({
  value,
  onChange,
  options,
  label,
  allLabel = "All",
  className,
  disabled,
}: {
  value: string;
  onChange: (value: string) => void;
  options: FilterOption[];
  label: string;
  allLabel?: string;
  className?: string;
  disabled?: boolean;
}) {
  return (
    <div className={cn("min-w-0", className)}>
      <label className="sr-only" htmlFor={`filter-${label}`}>
        {label}
      </label>
      <Select
        id={`filter-${label}`}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        className="h-9 text-small"
      >
        <option value="">{allLabel}</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
            {option.count !== undefined ? ` (${option.count})` : ""}
          </option>
        ))}
      </Select>
    </div>
  );
}

export function FilterBar({
  children,
  onReset,
  activeCount,
  className,
}: {
  children: React.ReactNode;
  onReset?: () => void;
  activeCount?: number;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-2.5 rounded-card border border-line bg-surface p-3 shadow-hairline",
        className,
      )}
      role="search"
    >
      {children}
      {onReset && activeCount ? (
        <Button variant="quiet" size="sm" onClick={onReset} className="ml-auto">
          Clear {activeCount} filter{activeCount > 1 ? "s" : ""}
        </Button>
      ) : null}
    </div>
  );
}
