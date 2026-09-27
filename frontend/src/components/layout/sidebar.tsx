"use client";

import { ChevronRight } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import * as React from "react";

import { useAuth } from "@/components/providers/auth-provider";
import { TelWordmark } from "@/components/layout/wordmark";
import { navigation, visibleGroups } from "@/components/layout/navigation";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * Desktop / tablet sidebar.
 *
 * A single flat list grouped by intent, with a persistent footer that shows who
 * is signed in. On tablet it collapses to an overlay drawer so the content
 * keeps the full width instead of being squeezed.
 */
export function Sidebar({
  onNavigate,
  className,
}: {
  onNavigate?: () => void;
  className?: string;
}) {
  const pathname = usePathname();
  const { user, can } = useAuth();
  const groups = React.useMemo(() => visibleGroups(navigation, can), [can]);

  return (
    <div className={cn("flex h-full flex-col bg-surface", className)}>
      <div className="px-5 pb-5 pt-6">
        <TelWordmark size="md" />
      </div>

      <nav aria-label="Main" className="no-scrollbar flex-1 overflow-y-auto px-3 pb-4">
        {groups.map((group) => (
          <div key={group.label} className="mb-5 last:mb-0">
            <p className="px-3 pb-2 text-caption font-semibold uppercase tracking-[0.12em] text-ink-faint">
              {group.label}
            </p>
            <ul className="flex flex-col gap-0.5">
              {group.items.map((item) => {
                const active =
                  pathname === item.href ||
                  (item.href !== "/dashboard" && pathname.startsWith(`${item.href}/`));
                const Icon = item.icon;
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      onClick={onNavigate}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "group relative flex items-center gap-3 rounded-control px-3 py-2.5 text-body transition-colors duration-200",
                        active
                          ? "bg-brand-tint font-medium text-brand-deep"
                          : "text-ink-soft hover:bg-surface-muted hover:text-ink",
                      )}
                    >
                      <span
                        aria-hidden
                        className={cn(
                          "absolute left-0 h-5 w-[3px] rounded-r-pill bg-brand transition-opacity duration-200",
                          active ? "opacity-100" : "opacity-0",
                        )}
                      />
                      <Icon
                        className={cn(
                          "h-[1.05rem] w-[1.05rem] shrink-0 transition-colors",
                          active ? "text-brand" : "text-ink-faint group-hover:text-ink-soft",
                        )}
                        aria-hidden
                      />
                      <span className="min-w-0 flex-1 truncate">{item.label}</span>
                      {active ? <ChevronRight className="h-3.5 w-3.5 text-brand/60" aria-hidden /> : null}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      {user?.profile ? (
        <div className="mx-3 mb-3 rounded-card border border-line-soft bg-surface-muted/70 p-3.5">
          <p className="text-caption font-semibold uppercase tracking-[0.1em] text-ink-faint">
            Enrolled at
          </p>
          <p className="mt-1 text-small font-medium leading-snug text-ink">
            {user.profile.class_display}
          </p>
          <p className="text-caption text-ink-muted">
            {[user.profile.campus?.name, user.profile.academic_year?.label]
              .filter(Boolean)
              .join(" · ")}
          </p>
          <p className="mt-2 font-mono text-caption text-ink-faint">{user.profile.student_code}</p>
        </div>
      ) : null}
    </div>
  );
}

/** Overlay wrapper used on tablet widths. */
export function SidebarDrawer({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  React.useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previous;
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 lg:hidden">
      <button
        type="button"
        aria-label="Close navigation"
        onClick={onClose}
        className="absolute inset-0 animate-fade-in bg-ink/25 backdrop-blur-[2px]"
      />
      <div className="absolute inset-y-0 left-0 w-[17rem] animate-slide-in border-r border-line bg-surface shadow-overlay">
        <Sidebar onNavigate={onClose} />
      </div>
    </div>
  );
}

export function MobileNavButton({ onClick }: { onClick: () => void }) {
  return (
    <Button variant="ghost" size="icon" onClick={onClick} aria-label="Open navigation" className="lg:hidden">
      <svg viewBox="0 0 20 20" className="h-5 w-5" aria-hidden>
        <path
          d="M3 5.5h14M3 10h14M3 14.5h14"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
        />
      </svg>
    </Button>
  );
}
