"use client";

import { Bell, LogOut, Settings, ShieldCheck, UserRound } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import * as React from "react";

import { useAuth } from "@/components/providers/auth-provider";
import { Button } from "@/components/ui/button";
import {
  Dropdown,
  DropdownContent,
  DropdownItem,
  DropdownLabel,
  DropdownSeparator,
  DropdownTrigger,
} from "@/components/ui/dropdown";
import { endpoints } from "@/lib/endpoints";
import { useResource } from "@/lib/hooks/use-resource";
import { cn } from "@/lib/utils";

const ROLE_LABEL: Record<string, string> = {
  STUDENT: "Student",
  CLASS_REPRESENTATIVE: "Class representative",
  TEACHER: "Teacher",
  ADMIN: "Administrator",
};

export function UserMenu() {
  const { user, logout, isRepresentative } = useAuth();
  const router = useRouter();
  const [signingOut, setSigningOut] = React.useState(false);

  if (!user) return null;

  return (
    <Dropdown>
      <DropdownTrigger asChild>
        <button
          type="button"
          className="flex items-center gap-2.5 rounded-control border border-transparent py-1 pl-1 pr-2 transition-colors duration-200 hover:border-line hover:bg-surface"
          aria-label={`Account menu for ${user.fullName}`}
        >
          <span className="flex h-8 w-8 items-center justify-center rounded-pill bg-brand-soft font-display text-small font-semibold text-brand-deep">
            {user.initials}
          </span>
          <span className="hidden min-w-0 text-left sm:block">
            <span className="block max-w-[9rem] truncate text-small font-medium text-ink">
              {user.fullName}
            </span>
            <span className="block text-caption text-ink-faint">
              {ROLE_LABEL[user.role] ?? user.role}
            </span>
          </span>
        </button>
      </DropdownTrigger>
      <DropdownContent className="min-w-[15rem]">
        <div className="px-3 py-2.5">
          <p className="truncate text-small font-medium text-ink">{user.fullName}</p>
          <p className="truncate text-caption text-ink-faint">{user.email}</p>
          {user.profile ? (
            <p className="mt-1.5 truncate text-caption text-ink-muted">
              {user.profile.student_code} · {user.profile.class_display}
            </p>
          ) : null}
          {isRepresentative ? (
            <p className="mt-2 inline-flex items-center gap-1.5 rounded-pill bg-brand-tint px-2 py-0.5 text-caption font-semibold text-brand-deep">
              <ShieldCheck className="h-3 w-3" aria-hidden />
              Timetable manager
            </p>
          ) : null}
        </div>
        <DropdownSeparator />
        <DropdownItem asChild>
          <Link href="/profile">
            <UserRound className="h-4 w-4" aria-hidden />
            My profile
          </Link>
        </DropdownItem>
        <DropdownItem asChild>
          <Link href="/profile#security">
            <Settings className="h-4 w-4" aria-hidden />
            Security
          </Link>
        </DropdownItem>
        {isRepresentative ? (
          <DropdownItem asChild>
            <Link href="/class-tools">
              <ShieldCheck className="h-4 w-4" aria-hidden />
              Class tools
            </Link>
          </DropdownItem>
        ) : null}
        <DropdownSeparator />
        <DropdownItem
          disabled={signingOut}
          onSelect={(event) => {
            event.preventDefault();
            setSigningOut(true);
            void logout().then(() => router.replace("/login"));
          }}
        >
          <LogOut className="h-4 w-4" aria-hidden />
          Sign out
        </DropdownItem>
      </DropdownContent>
    </Dropdown>
  );
}

export function NotificationBell() {
  const pathname = usePathname();
  const [isActive, setIsActive] = React.useState(pathname.startsWith("/notifications"));
  React.useEffect(() => setIsActive(pathname.startsWith("/notifications")), [pathname]);

  const { data, refetch } = useResource(
    (signal) => endpoints.notifications.unreadCount({ signal }),
    { deps: [pathname] },
  );
  const unread = data?.unread_count ?? 0;

  return (
    <Button
      asChild
      variant="ghost"
      size="icon"
      className="relative"
      aria-label={unread ? `Notifications, ${unread} unread` : "Notifications"}
    >
      <Link href="/notifications">
        <Bell className={cn("h-[1.15rem] w-[1.15rem]", isActive && "text-brand")} aria-hidden />
        {unread > 0 ? (
          <span className="absolute right-1.5 top-1.5 flex h-4 min-w-4 items-center justify-center rounded-pill bg-danger px-1 text-[0.5625rem] font-semibold text-white">
            {unread > 9 ? "9+" : unread}
          </span>
        ) : null}
        <span className="sr-only" onClick={() => refetch()} />
      </Link>
    </Button>
  );
}
