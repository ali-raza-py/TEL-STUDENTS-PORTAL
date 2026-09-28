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
import { subjectToken, formatPercent, formatMarks, formatDate, statusTone, gradeTone } from "@/lib/utils";
import { useResource, useDebounced } from "@/lib/hooks/use-resource";
import { endpoints } from "@/lib/endpoints";
import type { ResultRow, Paginated } from "@/lib/types";
import { PageTransitionWrapper } from "@/components/education/education-components";

export default function ResultsPage() {
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

  const { data, error, isLoading, refetch } = useResource(
    (signal) => endpoints.results.list(query, { signal }),
    { deps: [JSON.stringify(query)] },
  );

  function handleSearch(value: string) {
    setSearch(value);
    setPage(1);
  }

  const activeFilters = (debouncedSearch ? 1 : 0) + (subjectFilter ? 1 : 0) + (statusFilter ? 1 : 0);

  const statusOptions = [
    { value: "published", label: "Published" },
    { value: "pending", label: "Pending" },
    { value: "draft", label: "Draft" },
  ];

  return (
    <div className="relative min-h-[calc(100dvh-4rem)]">
      <PageTransitionWrapper>
        <PageStack>
          <PageHeader
            title="Results"
            description="Your assessment results and performance history."
          />

      <FilterBar
        onReset={() => { setSearch(""); setSubjectFilter(""); setStatusFilter(""); setPage(1); }}
        activeCount={activeFilters}
      >
        <SearchInput value={search} onChange={handleSearch} placeholder="Search results…" />
        <FilterSelect
          value={subjectFilter}
          onChange={(v) => { setSubjectFilter(v); setPage(1); }}
          options={subjectOptions(data)}
          label="Subject"
          allLabel="All subjects"
        />
        <FilterSelect
          value={statusFilter}
          onChange={(v) => { setStatusFilter(v); setPage(1); }}
          options={statusOptions}
          label="Status"
          allLabel="All statuses"
        />
      </FilterBar>

      {isLoading ? (
        <SkeletonList rows={6} />
      ) : error ? (
        <ErrorState error={error} onRetry={refetch} />
      ) : !data || data.results.length === 0 ? (
        <EmptyState
          title="No results found"
          description={
            activeFilters
              ? "Try clearing your filters to see all results."
              : "Your results will appear here once they are published."
          }
        />
      ) : (
        <>
          <SectionHeading title="Results" description={`${data.count} result${data.count !== 1 ? "s" : ""}`} />
          <div className="space-y-3">
            {data.results.map((result: ResultRow) => (
              <ResultCard key={result.id} result={result} />
            ))}
          </div>
          <Pagination
            page={data.page}
            numPages={data.num_pages}
            hasNext={data.has_next}
            hasPrevious={data.has_previous}
            onChange={setPage}
            label="Results navigation"
          />
        </>
      )}
    </PageStack>
    </PageTransitionWrapper>
  </div>
  );
}

function subjectOptions(data: Paginated<ResultRow> | null) {
  if (!data) return [];
  const unique = new Map<string, string>();
  data.results.forEach((r) => {
    if (!unique.has(r.subject_code)) unique.set(r.subject_code, r.subject_name);
  });
  return Array.from(unique, ([value, label]) => ({ value, label }));
}

function ResultCard({ result }: { result: ResultRow }) {
  const token = subjectToken(result.subject_color);
  const grade = result.grade || "";

  return (
    <Link href={`/results?highlight=${result.id}`}>
      <Card className="group p-5 transition-transform hover:scale-[1.01]">
        <CardHeader>
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <CardTitle className="flex items-center gap-2">
                <span className={token.dot} />
                {result.assessment_name}
              </CardTitle>
              <CardDescription>
                {result.subject_code} — {result.subject_name} ·{" "}
                {result.assessment_type_label} · {formatDate(result.assessment_date)}
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <ToneBadge tone={statusTone(result.status)}>
                {result.status_label}
              </ToneBadge>
              {grade && <Badge tone={gradeTone(grade)}>{grade}</Badge>}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-ink-muted">Obtained marks</p>
              <p className="text-lg font-semibold text-ink">
                {formatMarks(result.obtained_marks)}/{formatMarks(result.total_marks)}
              </p>
            </div>
            <div className="text-right">
              <p className="text-sm text-ink-muted">Percentage</p>
              <p className="text-lg font-semibold text-ink">{formatPercent(result.percentage, 1)}</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
