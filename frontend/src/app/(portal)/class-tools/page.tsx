"use client";

import { PageHeader, PageStack, SectionHeading } from "@/components/ui/page-header";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, Stat } from "@/components/ui/card";
import { Button, ButtonProps } from "@/components/ui/button";
import { SkeletonPage, Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { FileText, Upload, Eye } from "lucide-react";
import Link from "next/link";

import { useResource } from "@/lib/hooks/use-resource";
import { useAuth } from "@/components/providers/auth-provider";
import { endpoints } from "@/lib/endpoints";
import type { ClassToolkitAssignment } from "@/lib/types";
import { cn } from "@/lib/utils";

export default function ClassToolsPage() {
  const { user, can } = useAuth();
  const { data, error, isLoading, refetch } = useResource(
    (signal) => endpoints.academics.classToolkit({ signal }),
  );

  if (isLoading) return <SkeletonPage />;
  if (error) return <ErrorState error={error} onRetry={refetch} />;
  if (!data) return null;

  const canSubmitTimetable = can("submit_timetable");

  return (
    <PageStack>
      <PageHeader title="Class tools" description="Tools for managing your class." />

      <Card>
        <CardHeader>
          <CardTitle>Class overview</CardTitle>
          <CardDescription>
            {data.assignments.length > 0
              ? `${data.assignments.length} assignment${data.assignments.length !== 1 ? "s" : ""} assigned to your class`
              : "No information available"}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {data.assignments.length === 0 ? (
            <EmptyState
              title="No class assignments"
              description="No assignments have been assigned to your class yet."
              compact
            />
          ) : (
            <div className="space-y-3">
              {data.assignments.map((assignment: ClassToolkitAssignment) => (
                <Card key={`${assignment.class_id}-${assignment.section_id}`} className="p-4">
                  <div className="flex items-center justify-between gap-2">
                    <div>
                      <p className="font-medium text-ink">
                        {assignment.class_name} — Section {assignment.section_name}
                      </p>
                      <p className="text-caption text-ink-muted">
                        {assignment.subjects.length} subjects · Assigned {new Date(assignment.assigned_at).toLocaleDateString()}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-caption text-ink-faint">
                        Ends {assignment.ends_on ? new Date(assignment.ends_on).toLocaleDateString() : "—"}
                      </span>
                    </div>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {assignment.subjects.map((subject) => (
                      <span key={subject.subject__id} className="text-small text-ink-muted">
                        {subject.subject__code}: {subject.subject__name}
                      </span>
                    ))}
                  </div>
                </Card>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {canSubmitTimetable && (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Timetable</CardTitle>
              <CardDescription>
                Submit, review, and manage your class timetable.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-3 sm:grid-cols-2">
                <ToolButton href="/timetable/submissions" icon={<Upload className="h-4 w-4" />}>
                  Submit new timetable
                </ToolButton>
                <ToolButton href="/timetable" icon={<Eye className="h-4 w-4" />}>
                  View published timetable
                </ToolButton>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Report a timetable change</CardTitle>
              <CardDescription>
                Report changes to room, teacher, or timing for your class.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ToolButton href="/requests" icon={<FileText className="h-4 w-4" />}>
                Submit a request
              </ToolButton>
            </CardContent>
          </Card>
        </>
      )}
    </PageStack>
  );
}

function ToolButton({
  href,
  icon,
  children,
}: {
  href: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <Button asChild variant="secondary" className="h-auto justify-start p-3">
      <Link href={href}>
        <span className="flex items-center gap-2">
          {icon}
          {children}
        </span>
      </Link>
    </Button>
  );
}
