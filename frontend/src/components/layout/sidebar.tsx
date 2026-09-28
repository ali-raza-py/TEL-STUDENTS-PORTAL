"use client";

import { Menu } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import * as React from "react";

import { useAuth } from "@/components/providers/auth-provider";
import { TelWordmark } from "@/components/layout/wordmark";
import { navigation, visibleGroups, type NavGroup } from "@/components/layout/navigation";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * The navigation rail.
 *
 * Deliberately not a full-bleed browser bar: the left edge stays clean and
 * vertical while the right corners carry the radius, so the rail reads as a
 * separate frosted surface sitting *inside* the shell rather than a strip of
 * chrome welded to the window.
 *
 * Vertical rhythm follows the product's information order — wordmark, then
 * campus context, then grouped navigation, then flexible space, then the
 * pinned account group.
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
  const mainGroups = groups.filter((group) => !group.pinned);
  const footerGroups = groups.filter((group) => group.pinned);

  const context = user?.profile
    ? [user.profile.campus?.name, user.profile.academic_year?.label].filter(Boolean).join(" · ")
    : null;

  return (
    <div
      className={cn(
        "flex h-full flex-col overflow-hidden bg-[var(--frost-sidebar)] backdrop-blur-[var(--blur-rail)]",
        className,
      )}
    >
      {/* Wordmark + campus context. The context answers "which campus am I
          acting in?" without competing with the brand above it. */}
      <div className="px-5 pb-4 pt-6">
        <TelWordmark size="md" />
        {user?.profile ? (
          <div className="mt-4 rounded-control border border-line-soft bg-surface/70 px-3 py-2.5">
            <p className="text-label font-semibold uppercase text-ink-faint">Enrolled at</p>
            <p className="mt-1 text-small font-semibold leading-snug text-ink">
              {user.profile.class_display}
            </p>
            {context ? (
              <p className="mt-0.5 text-caption leading-snug text-ink-muted">{context}</p>
            ) : null}
          </div>
        ) : user ? (
          /* Staff have no student record, so show their role instead of an empty box. */
          <div className="mt-4 rounded-control border border-line-soft bg-surface/70 px-3 py-2.5">
            <p className="text-label font-semibold uppercase text-ink-faint">Signed in as</p>
            <p className="mt-1 text-small font-semibold leading-snug text-ink">
              {ROLE_LABELS[user.role] ?? user.role}
            </p>
            <p className="mt-0.5 truncate text-caption text-ink-muted">{user.email}</p>
          </div>
        ) : null}
      </div>

      <nav aria-label="Main" className="no-scrollbar flex-1 overflow-y-auto px-3 pb-2">
        {mainGroups.map((group) => (
          <NavGroupList key={group.label} group={group} activePath={pathname} onNavigate={onNavigate} />
        ))}
      </nav>

      {/* Flexible space, then the pinned account group. */}
      {footerGroups.length > 0 ? (
        <div className="border-t border-line-soft px-3 pb-3 pt-3">
          {footerGroups.map((group) => (
            <NavGroupList
              key={group.label}
              group={group}
              activePath={pathname}
              onNavigate={onNavigate}
              showLabel={footerGroups.length > 1}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}

function NavGroupList({
  group,
  activePath,
  onNavigate,
  showLabel = true,
}: {
  group: NavGroup;
  activePath: string;
  onNavigate?: () => void;
  showLabel?: boolean;
}) {
  return (
    <div className="mb-5 last:mb-0">
      {showLabel ? (
        <p className="px-3 pb-2 pt-1 text-label font-bold uppercase text-ink-faint">
          {group.label}
        </p>
      ) : null}
      <ul className="flex flex-col gap-0.5">
        {group.items.map((item) => (
          <NavItemLink key={item.href} item={item} activePath={activePath} onNavigate={onNavigate} />
        ))}
      </ul>
    </div>
  );
}

function NavItemLink({
  item,
  activePath,
  onNavigate,
}: {
  item: { href: string; label: string; icon: React.ElementType };
  activePath: string;
  onNavigate?: () => void;
}) {
  const active =
    activePath === item.href ||
    (item.href !== "/dashboard" && activePath.startsWith(`${item.href}/`));
  const Icon = item.icon;

  return (
    <li>
      <Link
        href={item.href}
        onClick={onNavigate}
        aria-current={active ? "page" : undefined}
        className={cn(
          "group relative flex min-h-11 items-center gap-3 rounded-control px-3 py-2.5",
          "text-nav transition-colors duration-150",
          active
            ? "bg-brand-tint font-semibold text-brand-deep"
            : "font-medium text-ink-soft hover:bg-surface-muted hover:text-ink",
        )}
      >
        {/* Side indicator — a short accent, not a full-height rule. */}
        <span
          aria-hidden
          className={cn(
            "absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-pill bg-brand transition-opacity duration-150",
            active ? "opacity-100" : "opacity-0",
          )}
        />
        <Icon
          className={cn(
            "size-[1.125rem] shrink-0 transition-colors duration-150",
            active ? "text-brand" : "text-ink-faint group-hover:text-ink-soft",
          )}
          aria-hidden
        />
        <span className="min-w-0 flex-1 truncate">{item.label}</span>
      </Link>
    </li>
  );
}

const ROLE_LABELS: Record<string, string> = {
  STUDENT: "Student",
  CLASS_REPRESENTATIVE: "Class representative",
  TEACHER: "Teacher",
  ADMIN: "Administrator",
};

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
        className="absolute inset-0 animate-fade-in bg-ink/30 backdrop-blur-[2px]"
      />
      {/* Floating sheet — same surface language as the desktop rail, with the
          right corners carrying the radius so it reads as a panel, not a wall. */}
      <div
        role="dialog"
        aria-label="Navigation"
        className="absolute inset-y-2 left-2 w-[17.5rem] animate-slide-in overflow-hidden rounded-[1.25rem] border border-line bg-surface shadow-overlay"
      >
        <Sidebar onNavigate={onClose} />
      </div>
    </div>
  );
}

export function MobileNavButton({ onClick }: { onClick: () => void }) {
  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={onClick}
      aria-label="Open navigation"
      className="lg:hidden"
    >
      <Menu className="size-5" aria-hidden />
    </Button>
  );
}
