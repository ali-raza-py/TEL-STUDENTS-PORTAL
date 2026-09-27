"use client";

import { useMemo, useState } from "react";
import Link from "next/link";

import { PageHeader, PageStack, SectionHeading } from "@/components/ui/page-header";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Badge, ToneBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Pagination } from "@/components/ui/tabs";
import { Skeleton, SkeletonPage } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { SearchInput, FilterBar, FilterSelect } from "@/components/ui/filter-bar";
import { subjectToken, formatPercent, formatDate, statusTone } from "@/lib/utils";
import { useResource, useDebounced } from "@/lib/hooks/use-resource";
import { endpoints } from "@/lib/endpoints";
import type { PaperSummary, Paginated } from "@/lib/types";
import { FloatingOrbs } from "@/components/education/education-components";

export default function PapersPage() {
  const [search, setSearch] = useState("");
  const [subjectFilter, setSubjectFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);

  const debouncedSearch = useDebounced(search, 320);

  const query = useMemo(() => {
    const q: Record<string, string | number | boolean | null | undefined> = { page };
    if (debouncedSearch) q.search = debouncedSearch;
    if (subjectFilter) q.subject_code = subjectFilter;
    if (statusFilter) q.status = statusFilter;
    return q;
  }, [debouncedSearch, subjectFilter, statusFilter, page]);

  const {
    data,
    error,
    isLoading,
    refetch,
  } = useResource(
    (signal) => endpoints.papers.list(query, { signal }),
    { deps: [JSON.stringify(query)] },
  );

  function handleSearch(value: string) {
    setSearch(value);
    setPage(1);
  }

  function handleSubject(value: string) {
    setSubjectFilter(value);
    setPage(1);
  }

  function handleStatus(value: string) {
    setStatusFilter(value);
    setPage(1);
  }

  const activeFilters = (debouncedSearch ? 1 : 0) + (subjectFilter ? 1 : 0) + (statusFilter ? 1 : 0);

  const statusOptions = [
    { value: "published", label: "Published" },
    { value: "draft", label: "Draft" },
    { value: "pending", label: "Pending" },
  ];

  return (
    <div className="relative min-h-[calc(100dvh-4rem)]">
      <FloatingOrbs count={3} color="info" opacity={0.03} />
      <PageStack className="relative z-10">
        <PageHeader
          title="Papers"
          description="Past exam papers and practice sessions."
        />

      <FilterBar onReset={() => { setSearch(""); setSubjectFilter(""); setStatusFilter(""); setPage(1); }} activeCount={activeFilters}>
        <SearchInput
          value={search}
          onChange={handleSearch}
          placeholder="Search papers…"
        />
        <FilterSelect
          value={subjectFilter}
          onChange={handleSubject}
          options={subjectOptions(data)}
          label="Subject"
          allLabel="All subjects"
        />
        <FilterSelect
          value={statusFilter}
          onChange={handleStatus}
          options={statusOptions}
          label="Status"
          allLabel="All statuses"
        />
      </FilterBar>

      {isLoading ? (
        <SkeletonPage />
      ) : error ? (
        <ErrorState error={error} onRetry={refetch} />
      ) : !data || data.results.length === 0 ? (
        <EmptyState
          title="No papers found"
          description={
            activeFilters
              ? "Try clearing your filters to see all papers."
              : "No papers are available for your class yet."
          }
        />
      ) : (
        <>
          <div className="space-y-3">
            {data.results.map((paper: PaperSummary) => (
              <PaperCard key={paper.id} paper={paper} />
            ))}
          </div>
          <Pagination
            page={data.page}
            numPages={data.num_pages}
            hasNext={data.has_next}
            hasPrevious={data.has_previous}
            onChange={setPage}
            label="Papers navigation"
          />
        </>
      )}
    </PageStack>
    </div>
  );
}

function subjectOptions(data: Paginated<PaperSummary> | null) {
  if (!data) return [];
  const unique = new Map<string, string>();
  data.results.forEach((p) => {
    if (!unique.has(p.subject_code)) unique.set(p.subject_code, p.subject_name);
  });
  return Array.from(unique, ([value, label]) => ({ value, label }));
}

function PaperCard({ paper }: { paper: PaperSummary }) {
  const token = subjectToken(paper.subject_color);
  const hasAttempt = paper.latest_attempt_percentage !== null;
  const progressPct = paper.best_attempt_percentage ?? 0;

  return (
    <Link href={`/papers/${paper.id}`}>
      <Card className="group p-5 transition-transform hover:scale-[1.01]">
        <CardHeader>
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <CardTitle className="flex items-center gap-2">
                <span className={token.dot} />
                {paper.title}
              </CardTitle>
              <CardDescription>
                {paper.subject_code} — {paper.subject_name} · {paper.exam_type_label}
              </CardDescription>
            </div>
            <ToneBadge tone={statusTone(paper.status)}>
              {paper.status_label}
            </ToneBadge>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4 text-small sm:grid-cols-4">
            <div>
              <span className="text-ink-faint">Total marks</span>
              <span className="ml-1 font-medium text-ink">{paper.total_marks}</span>
            </div>
            <div>
              <span className="text-ink-faint">Duration</span>
              <span className="ml-1 font-medium text-ink">{paper.duration_minutes} min</span>
            </div>
            {paper.exam_date && (
              <div>
                <span className="text-ink-faint">Exam date</span>
                <span className="ml-1 font-medium text-ink">{formatDate(paper.exam_date)}</span>
              </div>
            )}
            <div>
              <span className="text-ink-faint">Teacher</span>
              <span className="ml-1 font-medium text-ink">{paper.teacher_name || "—"}</span>
            </div>
          </div>

          {hasAttempt && (
            <div className="mt-3 flex items-center gap-3">
              <span className="text-caption text-ink-muted">Best attempt: {formatPercent(progressPct)}</span>
              {paper.attempts_remaining !== null && (
                <span className="text-caption text-ink-muted">
                  {paper.attempts_remaining} attempts left
                </span>
              )}
            </div>
          )}

          {paper.can_practice && (
            <Button
              asChild
              variant="soft"
              size="sm"
              className="mt-3"
              icon={null}
            >
              <Link href={`/practice/${paper.id}`}>Start practice</Link>
            </Button>
          )}
        </CardContent>
      </Card>
    </Link>
  );
}

function PaperSkeletonList({ rows = 4 }: { rows?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }).map((_, i) => (
        <Card key={i} className="p-5">
          <Skeleton className="h-5 w-3/4" />
          <Skeleton className="mt-2 h-3 w-1/2" />
          <div className="mt-3 grid grid-cols-2 gap-4">
            <Skeleton className="h-3 w-16" />
            <Skeleton className="h-3 w-20" />
          </div>
        </Card>
      ))}
    </div>
  );
}
