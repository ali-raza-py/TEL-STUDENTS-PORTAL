"use client";

import { usePathname } from "next/navigation";
import * as React from "react";

import { MobileBottomNav } from "@/components/layout/mobile-nav";
import { NotificationBell, UserMenu } from "@/components/layout/user-menu";
import { Sidebar, SidebarDrawer, MobileNavButton } from "@/components/layout/sidebar";
import { TelWordmark } from "@/components/layout/wordmark";
import { useAuth } from "@/components/providers/auth-provider";
import { Skeleton } from "@/components/ui/skeleton";
import { navigation, visibleGroups } from "@/components/layout/navigation";
import type { Capability } from "@/lib/session-types";
import { cn } from "@/lib/utils";

/** Human labels for the breadcrumb trail. */
const CRUMBS: Record<string, string> = {
  dashboard: "Dashboard",
  timetable: "Timetable",
  subjects: "Subjects",
  papers: "Papers",
  practice: "Practice",
  results: "Results",
  attendance: "Attendance",
  assignments: "Assignments",
  resources: "Resources",
  announcements: "Announcements",
  notifications: "Notifications",
  calendar: "Calendar",
  requests: "Requests",
  feedback: "Feedback",
  profile: "Profile",
  "class-tools": "Class tools",
};

function Breadcrumbs() {
  const pathname = usePathname();
  const { can } = useAuth();
  const groups = React.useMemo(() => visibleGroups(navigation, can), [can]);

  const segments = pathname.split("/").filter(Boolean);
  if (segments.length === 0) return null;

  const group = groups.find((g) => g.items.some((item) => item.href === `/${segments[0]}`));
  const root = group?.items.find((item) => item.href === `/${segments[0]}`);

  return (
    <nav aria-label="Breadcrumb" className="hidden items-center gap-1.5 text-caption text-ink-faint sm:flex">
      <span>{group?.label ?? "Portal"}</span>
      <span aria-hidden>/</span>
      <span className="font-medium text-ink-soft">{CRUMBS[segments[0]] ?? root?.label ?? segments[0]}</span>
      {segments.length > 1 ? (
        <>
          <span aria-hidden>/</span>
          <span className="max-w-[10rem] truncate font-medium text-ink-soft">Detail</span>
        </>
      ) : null}
    </nav>
  );
}

function ShellSkeleton() {
  return (
    <div className="flex min-h-dvh" aria-busy="true" aria-label="Loading the portal">
      <div className="hidden w-[16.5rem] shrink-0 border-r border-line bg-surface p-5 lg:block">
        <Skeleton className="h-9 w-40" />
        <div className="mt-8 space-y-6">
          {Array.from({ length: 4 }).map((_, group) => (
            <div key={group} className="space-y-2">
              <Skeleton className="h-2.5 w-16" />
              {Array.from({ length: 3 }).map((_, item) => (
                <Skeleton key={item} className="h-9 w-full" />
              ))}
            </div>
          ))}
        </div>
      </div>
      <div className="flex-1 px-4 py-6 sm:px-6 lg:px-9">
        <Skeleton className="h-8 w-56" />
        <div className="mt-7 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <Skeleton key={index} className="h-40 rounded-card" />
          ))}
        </div>
      </div>
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { status } = useAuth();
  const [drawerOpen, setDrawerOpen] = React.useState(false);
  const pathname = usePathname();

  React.useEffect(() => {
    setDrawerOpen(false);
  }, [pathname]);

  if (status === "loading") return <ShellSkeleton />;

  return (
    <div className="min-h-dvh bg-canvas">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-[70] focus:rounded-control focus:bg-surface focus:px-4 focus:py-2 focus:text-body focus:shadow-overlay"
      >
        Skip to main content
      </a>

      {/* Desktop rail */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-[16.5rem] border-r border-line lg:block">
        <Sidebar />
      </aside>

      {/* Tablet / mobile drawer */}
      <SidebarDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} />

      <div className="lg:pl-[16.5rem]">
        <header className="sticky top-0 z-20 border-b border-line bg-canvas/85 backdrop-blur-md">
          <div className="flex h-16 items-center gap-3 px-4 sm:px-6 lg:px-9">
            <MobileNavButton onClick={() => setDrawerOpen(true)} />
            <div className="lg:hidden">
              <TelWordmark size="sm" showSubtitle={false} />
            </div>
            <div className="hidden lg:block">
              <Breadcrumbs />
            </div>
            <div className="ml-auto flex items-center gap-1.5">
              <NotificationBell />
              <UserMenu />
            </div>
          </div>
        </header>

        <main
          id="main"
          tabIndex={-1}
          className={cn(
            "mx-auto w-full max-w-[92rem] px-4 pb-28 pt-6 outline-none sm:px-6 lg:px-9 lg:pb-14 lg:pt-8",
          )}
        >
          {children}
        </main>
      </div>

      <MobileBottomNav />
    </div>
  );
}
