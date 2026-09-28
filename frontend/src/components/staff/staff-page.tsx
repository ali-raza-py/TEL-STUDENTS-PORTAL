"use client";

import * as React from "react";
import { Lock } from "lucide-react";

import { useAuth } from "@/components/providers/auth-provider";
import { PageHeader, PageStack } from "@/components/ui/page-header";
import { EmptyState } from "@/components/ui/states";
import type { Capability } from "@/lib/session-types";

/**
 * Shared shell for every staff page.
 *
 * Two jobs, both of which would otherwise be repeated in each page:
 *
 * 1. Refuse to render for a caller without the capability. The API enforces the
 *    same rule, so this is not the control — it just avoids showing a page that
 *    would immediately fail its own data fetch.
 * 2. Fix one page rhythm: header, then content.
 */
export function StaffPage({
  capability,
  title,
  description,
  actions,
  eyebrow = "Staff",
  children,
}: {
  capability: Capability;
  title: string;
  description?: string;
  actions?: React.ReactNode;
  eyebrow?: string;
  children: React.ReactNode;
}) {
  const { can } = useAuth();

  if (!can(capability)) {
    return (
      <PageStack>
        <PageHeader title={title} description={description} />
        <EmptyState
          title="Not available for your role"
          description="This area is limited to TEL staff. If you need access, contact your administrator."
          icon={<Lock className="h-5 w-5" aria-hidden />}
        />
      </PageStack>
    );
  }

  return (
    <PageStack>
      <PageHeader eyebrow={eyebrow} title={title} description={description} actions={actions} />
      {children}
    </PageStack>
  );
}
