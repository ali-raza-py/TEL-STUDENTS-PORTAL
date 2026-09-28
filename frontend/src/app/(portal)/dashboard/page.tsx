"use client";

import { PageHeader, PageStack } from "@/components/ui/page-header";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { Skeleton, SkeletonStats, SkeletonCard } from "@/components/ui/skeleton";
import { useResource } from "@/lib/hooks/use-resource";
import { endpoints } from "@/lib/endpoints";
import type {
  AdminDashboard,
  DashboardData,
  DashboardUnavailable,
  TeacherDashboard,
} from "@/lib/types";
import { AdminDashboardView } from "./admin-dashboard";
import { StudentDashboard } from "./student-dashboard";
import { TeacherDashboardView } from "./teacher-dashboard";

/**
 * One dashboard route, three payloads.
 *
 * The API shapes the dashboard by role and every payload carries a discriminator
 * — a `role` for staff, the student keys otherwise — so the role is read from
 * the response rather than guessed from client state. That keeps the client from
 * ever rendering a view the server would not have sent.
 */
type DashboardPayload =
  | DashboardData
  | TeacherDashboard
  | AdminDashboard
  | DashboardUnavailable;

function isUnavailable(payload: DashboardPayload): payload is DashboardUnavailable {
  return "available" in payload && payload.available === false;
}

function isAdmin(payload: DashboardPayload): payload is AdminDashboard {
  return "role" in payload && payload.role === "ADMIN";
}

function isTeacher(payload: DashboardPayload): payload is TeacherDashboard {
  return "role" in payload && payload.role === "TEACHER";
}

export default function DashboardPage() {
  const { data, error, isLoading, refetch } = useResource<DashboardPayload>((signal) =>
    endpoints.dashboard.get({ signal }),
  );

  if (isLoading) return <DashboardSkeleton />;
  if (error) return <ErrorState error={error} onRetry={refetch} />;
  if (!data) return null;

  if (isAdmin(data)) return <AdminDashboardView data={data} />;
  if (isTeacher(data)) return <TeacherDashboardView data={data} />;
  if (isUnavailable(data)) {
    return (
      <PageStack>
        <PageHeader title="Dashboard" description={data.message} />
        <EmptyState title="Dashboard not available yet" description={data.message} />
      </PageStack>
    );
  }

  return <StudentDashboard data={data as DashboardData} />;
}

function DashboardSkeleton() {
  return (
    <PageStack>
      <PageHeader title="Dashboard" description="Loading your overview…" />
      <SkeletonStats count={4} />
      <div className="space-y-3">
        <Skeleton className="h-4 w-32" />
        <div className="grid gap-2.5 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      </div>
    </PageStack>
  );
}
