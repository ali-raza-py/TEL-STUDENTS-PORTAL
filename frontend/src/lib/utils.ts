import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/* -------------------------------------------------------------------------- */
/* Numbers & dates                                                            */
/* -------------------------------------------------------------------------- */

export function formatPercent(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${value.toFixed(digits)}%`;
}

export function formatMarks(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

export function formatFileSize(bytes: number | null | undefined): string {
  if (!bytes) return "—";
  const units = ["B", "KB", "MB", "GB"];
  let size = bytes;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  return `${size.toFixed(size >= 10 || unit === 0 ? 0 : 1)} ${units[unit]}`;
}

const DATE_FMT = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  year: "numeric",
});
const DATE_LONG_FMT = new Intl.DateTimeFormat("en-GB", {
  weekday: "long",
  day: "numeric",
  month: "long",
  year: "numeric",
});
const TIME_FMT = new Intl.DateTimeFormat("en-GB", {
  hour: "2-digit",
  minute: "2-digit",
  hour12: true,
});

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return DATE_FMT.format(date);
}

export function formatLongDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return DATE_LONG_FMT.format(date);
}

export function formatTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return TIME_FMT.format(date).replace(/^0/, "");
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return `${DATE_FMT.format(date)} · ${TIME_FMT.format(date).replace(/^0/, "")}`;
}

/** "3 days ago", "in 2 weeks" — used for announcements and notifications. */
export function formatRelative(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  const diffMs = date.getTime() - Date.now();
  const abs = Math.abs(diffMs);
  const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  const minute = 60_000;
  const hour = 60 * minute;
  const day = 24 * hour;
  const week = 7 * day;
  if (abs < hour) return rtf.format(Math.round(diffMs / minute), "minute");
  if (abs < day) return rtf.format(Math.round(diffMs / hour), "hour");
  if (abs < week) return rtf.format(Math.round(diffMs / day), "day");
  if (abs < 30 * day) return rtf.format(Math.round(diffMs / week), "week");
  if (abs < 365 * day) return rtf.format(Math.round(diffMs / (30 * day)), "month");
  return rtf.format(Math.round(diffMs / (365 * day)), "year");
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "—";
  const safe = Math.max(0, Math.round(seconds));
  const minutes = Math.floor(safe / 60);
  const rest = safe % 60;
  if (minutes === 0) return `${rest}s`;
  return `${minutes}m ${String(rest).padStart(2, "0")}s`;
}

export function isoDateInput(value: Date): string {
  return value.toISOString().slice(0, 10);
}

/* -------------------------------------------------------------------------- */
/* Presentation helpers                                                       */
/* -------------------------------------------------------------------------- */

export type Tone = "brand" | "success" | "warning" | "danger" | "info" | "neutral";

export const toneClasses: Record<Tone, string> = {
  brand: "bg-brand-tint text-brand-deep border-brand-soft",
  success: "bg-success-soft text-success border-success-soft",
  warning: "bg-warning-soft text-warning border-warning-soft",
  danger: "bg-danger-soft text-danger border-danger-soft",
  info: "bg-info-soft text-info border-info-soft",
  neutral: "bg-surface-muted text-ink-soft border-line",
};

export const subjectTokenClasses: Record<string, { text: string; bg: string; dot: string; bar: string }> = {
  sage: { text: "text-subject-sage", bg: "bg-subject-sage-soft", dot: "bg-subject-sage", bar: "bg-subject-sage" },
  mint: { text: "text-subject-mint", bg: "bg-subject-mint-soft", dot: "bg-subject-mint", bar: "bg-subject-mint" },
  sky: { text: "text-subject-sky", bg: "bg-subject-sky-soft", dot: "bg-subject-sky", bar: "bg-subject-sky" },
  sand: { text: "text-subject-sand", bg: "bg-subject-sand-soft", dot: "bg-subject-sand", bar: "bg-subject-sand" },
  clay: { text: "text-subject-clay", bg: "bg-subject-clay-soft", dot: "bg-subject-clay", bar: "bg-subject-clay" },
  lilac: { text: "text-subject-lilac", bg: "bg-subject-lilac-soft", dot: "bg-subject-lilac", bar: "bg-subject-lilac" },
};

export function subjectToken(token: string | null | undefined) {
  return subjectTokenClasses[token ?? "sage"] ?? subjectTokenClasses.sage;
}

export function initialsOf(name: string | null | undefined): string {
  if (!name) return "ST";
  return name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0] ?? "")
    .join("")
    .toUpperCase();
}

export function pluralise(count: number, singular: string, plural?: string): string {
  return `${count} ${count === 1 ? singular : (plural ?? `${singular}s`)}`;
}

export function gradeTone(grade: string): Tone {
  if (!grade) return "neutral";
  const letter = grade[0].toUpperCase();
  if (letter === "A") return "success";
  if (letter === "B" || letter === "C") return "brand";
  if (letter === "D") return "warning";
  return "danger";
}

export function percentageTone(value: number | null, target: number): Tone {
  if (value === null) return "neutral";
  if (value >= target + 10) return "success";
  if (value >= target) return "brand";
  if (value >= target - 10) return "warning";
  return "danger";
}

export function statusTone(status: string): Tone {
  switch (status) {
    case "PUBLISHED":
    case "APPROVED":
    case "RESOLVED":
    case "REVIEWED":
    case "PRACTICE_AVAILABLE":
    case "VERIFIED":
      return "success";
    case "SUBMITTED":
    case "PENDING":
    case "IN_REVIEW":
    case "IN_PROGRESS":
    case "UNDER_REVIEW":
      return "warning";
    case "REJECTED":
    case "ARCHIVED":
    case "LATE":
      return "danger";
    case "CHANGES_REQUESTED":
    case "NOT_STARTED":
      return "info";
    default:
      return "neutral";
  }
}
