"use client";

import { useState, useMemo } from "react";
import Link from "next/link";

import { PageHeader, PageStack, SectionHeading } from "@/components/ui/page-header";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Badge, ToneBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Pagination } from "@/components/ui/tabs";
import { SkeletonPage, SkeletonList } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { SearchInput, FilterBar, FilterSelect } from "@/components/ui/filter-bar";
import { subjectToken, formatDate, formatPercent, type Tone } from "@/lib/utils";
import { useResource, useDebounced } from "@/lib/hooks/use-resource";
import { endpoints } from "@/lib/endpoints";
import type { AssignmentRow, Paginated } from "@/lib/types";
import { FloatingOrbs, PageTransitionWrapper } from "@/components/education/education-components";

export default function AssignmentsPage() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);

  const debouncedSearch = useDebounced(search, 320);

  const query = useMemo(() => {
    const q: Record<string, string | number | boolean | null | undefined> = { page };
    if (debouncedSearch) q.search = debouncedSearch;
    if (statusFilter) q.status = statusFilter;
    return q;
  }, [debouncedSearch, statusFilter, page]);

  const { data, error, isLoading, refetch } = useResource(
    (signal) => endpoints.engagement.assignments(query, { signal }),
    { deps: [JSON.stringify(query)] },
  );

  const activeFilters = (debouncedSearch ? 1 : 0) + (statusFilter ? 1 : 0);

  const statusOptions = [
    { value: "NOT_STARTED", label: "Not started" },
    { value: "IN_PROGRESS", label: "In progress" },
    { value: "SUBMITTED", label: "Submitted" },
    { value: "LATE", label: "Overdue" },
    { value: "REVIEWED", label: "Reviewed" },
  ];

  return (
    <div className="relative min-h-[calc(100dvh-4rem)]">
      <FloatingOrbs opacity={0.04} color="warning" count={4} />
      <PageTransitionWrapper>
        <PageStack>
          <PageHeader title="Assignments" description="Your class assignments and submissions." />

      <FilterBar
        onReset={() => { setSearch(""); setStatusFilter(""); setPage(1); }}
        activeCount={activeFilters}
      >
        <SearchInput value={search} onChange={(v) => { setSearch(v); setPage(1); }} placeholder="Search assignments…" />
        <FilterSelect
          value={statusFilter}
          onChange={(v) => { setStatusFilter(v); setPage(1); }}
          options={statusOptions}
          label="Status"
          allLabel="All statuses"
        />
      </FilterBar>

      {isLoading ? (
        <SkeletonList rows={5} />
      ) : error ? (
        <ErrorState error={error} onRetry={refetch} />
      ) : !data || data.results.length === 0 ? (
        <EmptyState
          title="No assignments found"
          description={activeFilters ? "Try clearing your filters." : "Check back later for new assignments."}
        />
      ) : (
        <>
          <div className="space-y-3">
            {data.results.map((assignment: AssignmentRow) => (
              <Link key={assignment.id} href={`/assignments/${assignment.id}`}>
                <Card className="group p-5 transition-transform hover:scale-[1.01]">
                  <CardHeader>
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <CardTitle className="flex items-center gap-2">
                          <span className={subjectToken(assignment.subject_color).dot} />
                          {assignment.title}
                        </CardTitle>
                        <CardDescription>
                          {assignment.subject_code} — {assignment.subject_name} · Teacher: {assignment.teacher_name}
                        </CardDescription>
                      </div>
                        <ToneBadge tone={assignmentStatusTone(assignment.status)}>
                        {assignment.status.replace("_", " ")}
                      </ToneBadge>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="grid gap-2 text-small sm:grid-cols-2">
                      <div>
                        <span className="text-ink-faint">Due</span>
                        <span className="ml-1 font-medium text-ink">{formatDate(assignment.due_on)}</span>
                      </div>
                      <div>
                        <span className="text-ink-faint">Max marks</span>
                        <span className="ml-1 font-medium text-ink">{assignment.max_marks}</span>
                      </div>
                      {assignment.is_overdue && (
                        <div className="sm:col-span-2">
                          <Badge tone="danger">Overdue</Badge>
                        </div>
                      )}
                      {assignment.submission && assignment.submission.file_url && (
                        <div className="sm:col-span-2">
                          <a
                            href={assignment.submission.file_url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-small font-medium text-brand underline underline-offset-2"
                          >
                            View your submission
                          </a>
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
          <Pagination
            page={data.page}
            numPages={data.num_pages}
            hasNext={data.has_next}
            hasPrevious={data.has_previous}
            onChange={setPage}
            label="Assignments navigation"
          />
        </>
      )}
    </PageStack>
    </PageTransitionWrapper>
    </div>
  );
}

function assignmentStatusTone(status: string): Tone {
  const s = status.toUpperCase();
  switch (s) {
    case "SUBMITTED":
    case "REVIEWED":
      return "success";
    case "IN_PROGRESS":
      return "warning";
    case "LATE":
      return "danger";
    case "NOT_STARTED":
      return "info";
    default:
      return "neutral";
  }
}
