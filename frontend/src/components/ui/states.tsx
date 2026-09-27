import { AlertTriangle, Inbox, RefreshCw, WifiOff } from "lucide-react";
import * as React from "react";

import { ApiError } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import { Button } from "./button";

/**
 * Empty and error states.
 *
 * Both are first class: a module with no data says so and offers the next
 * useful action, and a failed request never shows a blank screen.
 */

export function EmptyState({
  title,
  description,
  icon,
  action,
  secondaryAction,
  className,
  compact = false,
}: {
  title: string;
  description?: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
  secondaryAction?: React.ReactNode;
  className?: string;
  compact?: boolean;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-card border border-dashed border-line-strong bg-surface-muted/60 text-center",
        compact ? "gap-2 px-5 py-8" : "gap-3 px-6 py-14",
        className,
      )}
    >
      <span className="flex h-11 w-11 items-center justify-center rounded-pill bg-brand-tint text-brand">
        {icon ?? <Inbox className="h-5 w-5" aria-hidden />}
      </span>
      <p className="font-display text-h3 text-ink">{title}</p>
      {description ? (
        <p className="max-w-sm text-small text-ink-muted">{description}</p>
      ) : null}
      {action || secondaryAction ? (
        <div className="mt-2 flex flex-wrap items-center justify-center gap-2">
          {action}
          {secondaryAction}
        </div>
      ) : null}
    </div>
  );
}

function errorHeadline(error: ApiError): { title: string; description: string; icon: React.ReactNode } {
  if (error.status === 0) {
    return {
      title: "Unable to reach the portal",
      description:
        "We could not connect to the TEL portal service. Check your connection, then try again.",
      icon: <WifiOff className="h-5 w-5" aria-hidden />,
    };
  }
  if (error.isAuth) {
    return {
      title: "Your session has expired",
      description: "Please sign in again to continue where you left off.",
      icon: <AlertTriangle className="h-5 w-5" aria-hidden />,
    };
  }
  if (error.isForbidden) {
    return {
      title: "You do not have access to this",
      description: error.message || "This area is not available for your role.",
      icon: <AlertTriangle className="h-5 w-5" aria-hidden />,
    };
  }
  if (error.isNotFound) {
    return {
      title: "We could not find that",
      description: error.message || "The record may have been moved or removed.",
      icon: <Inbox className="h-5 w-5" aria-hidden />,
    };
  }
  return {
    title: "Something went wrong",
    description: error.message || "Please try again in a moment.",
    icon: <AlertTriangle className="h-5 w-5" aria-hidden />,
  };
}

export function ErrorState({
  error,
  onRetry,
  className,
  compact = false,
}: {
  error: ApiError;
  onRetry?: () => void;
  className?: string;
  compact?: boolean;
}) {
  const { title, description, icon } = errorHeadline(error);
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-start gap-3 rounded-card border border-danger-soft bg-danger-soft/40 p-5",
        compact && "p-4",
        className,
      )}
    >
      <div className="flex items-start gap-3">
        <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-pill bg-surface text-danger">
          {icon}
        </span>
        <div className="min-w-0">
          <p className="font-display text-h3 text-ink">{title}</p>
          <p className="mt-1 text-small text-ink-soft">{description}</p>
          {error.traceId ? (
            <p className="mt-2 font-mono text-caption text-ink-faint">
              Reference: {error.traceId}
            </p>
          ) : null}
        </div>
      </div>
      {onRetry ? (
        <Button variant="secondary" size="sm" onClick={onRetry} icon={<RefreshCw className="h-3.5 w-3.5" />}>
          Try again
        </Button>
      ) : null}
    </div>
  );
}

/** Inline variant for a section that failed while the rest of the page loaded. */
export function InlineError({
  message,
  onRetry,
  className,
}: {
  message: string;
  onRetry?: () => void;
  className?: string;
}) {
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-wrap items-center gap-3 rounded-control border border-danger-soft bg-danger-soft/40 px-4 py-3 text-small text-ink-soft",
        className,
      )}
    >
      <AlertTriangle className="h-4 w-4 shrink-0 text-danger" aria-hidden />
      <span className="min-w-0 flex-1">{message}</span>
      {onRetry ? (
        <Button variant="ghost" size="sm" onClick={onRetry}>
          Retry
        </Button>
      ) : null}
    </div>
  );
}
