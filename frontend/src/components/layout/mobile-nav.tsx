"use client";

import { usePathname } from "next/navigation";
import * as React from "react";

import { useAuth } from "@/components/providers/auth-provider";
import { mobileNavigation } from "@/components/layout/navigation";
import { cn } from "@/lib/utils";

/**
 * Mobile bottom navigation.
 *
 * Mobile is a redesign rather than a squeeze: only the five things a student
 * opens daily get a slot here, and everything else lives behind the drawer.
 */
export function MobileBottomNav() {
  const pathname = usePathname();
  const { can } = useAuth();
  const items = React.useMemo(
    () => mobileNavigation.filter((item) => !item.capability || can(item.capability)),
    [can],
  );

  return (
    <nav
      aria-label="Primary"
      className="fixed inset-x-0 bottom-0 z-40 border-t border-line bg-surface/95 backdrop-blur-md lg:hidden"
      style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
    >
      <ul className="mx-auto flex max-w-lg items-stretch">
        {items.map((item) => {
          const Icon = item.icon;
          const active =
            pathname === item.href || pathname.startsWith(`${item.href}/`);
          return (
            <li key={item.href} className="flex-1">
              <a
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex flex-col items-center gap-1 px-1 py-2.5 text-[0.625rem] transition-colors duration-200",
                  active ? "font-semibold text-brand" : "font-medium text-ink-faint",
                )}
              >
                <span
                  className={cn(
                    "flex h-7 w-12 items-center justify-center rounded-pill transition-colors duration-200",
                    active && "bg-brand-tint",
                  )}
                >
                  <Icon className="size-[1.125rem]" aria-hidden />
                </span>
                {item.label}
              </a>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
