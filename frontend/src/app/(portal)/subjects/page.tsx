"use client";

import Link from "next/link";

import { PageHeader, PageStack, SectionHeading } from "@/components/ui/page-header";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { SkeletonPage } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { subjectToken } from "@/lib/utils";
import { useResource } from "@/lib/hooks/use-resource";
import { endpoints } from "@/lib/endpoints";
import type { SubjectOffering } from "@/lib/types";
import { FloatingOrbs, PageTransitionWrapper } from "@/components/education/education-components";

export default function SubjectsPage() {
  const {
    data,
    error,
    isLoading,
    refetch,
  } = useResource((signal) =>
    endpoints.academics.subjects({ signal }),
  );

  if (isLoading) return <SkeletonPage />;
  if (error) return <ErrorState error={error} onRetry={refetch} />;
  if (!data) return null;

  const subjects = data.results;

  return (
    <div className="relative min-h-[calc(100dvh-4rem)]">
      <FloatingOrbs opacity={0.04} color="brand" count={4} />
      <PageTransitionWrapper>
        <PageStack>
          <PageHeader
            title="My Subjects"
            description="Subjects enrolled for your current class."
          />

          {subjects.length === 0 ? (
            <EmptyState
              title="No subjects found"
              description="Your class does not have any subjects assigned yet."
            />
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {subjects.map((subject: SubjectOffering) => {
                const token = subjectToken(subject.subject_kind);
                return (
                  <Link key={subject.subject_id} href={`/papers?subject=${subject.subject_code}`}>
                    <Card className="group p-5 transition-transform hover:scale-[1.02]">
                      <CardHeader>
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <CardTitle>{subject.subject_name}</CardTitle>
                            <CardDescription>{subject.subject_code}</CardDescription>
                          </div>
                          <Badge tone="neutral" className={token.bg}>
                            {subject.subject_kind ?? "Core"}
                          </Badge>
                        </div>
                      </CardHeader>
                      <CardContent>
                        <div className="grid grid-cols-2 gap-3 text-small">
                          <div>
                            <span className="text-ink-faint">Papers</span>
                            <span className="ml-1 font-medium text-ink">{subject.paper_count}</span>
                          </div>
                          <div>
                            <span className="text-ink-faint">Resources</span>
                            <span className="ml-1 font-medium text-ink">{subject.resource_count}</span>
                          </div>
                          {subject.teacher_name && (
                            <div className="col-span-2">
                              <span className="text-ink-faint">Teacher</span>
                              <span className="ml-1 font-medium text-ink">{subject.teacher_name}</span>
                            </div>
                          )}
                        </div>
                      </CardContent>
                    </Card>
                  </Link>
                );
              })}
            </div>
          )}
        </PageStack>
      </PageTransitionWrapper>
    </div>
  );
}
