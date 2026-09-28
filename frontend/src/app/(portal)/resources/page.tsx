"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { Download, ExternalLink } from "lucide-react";

import { PageHeader, PageStack, SectionHeading } from "@/components/ui/page-header";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Badge, ToneBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Pagination } from "@/components/ui/tabs";
import { SkeletonPage, SkeletonList } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { SearchInput, FilterBar, FilterSelect } from "@/components/ui/filter-bar";
import { subjectToken, formatFileSize } from "@/lib/utils";
import { useResource, useDebounced } from "@/lib/hooks/use-resource";
import { endpoints } from "@/lib/endpoints";
import type { ResourceRow, Paginated } from "@/lib/types";
import { FloatingOrbs, PageTransitionWrapper } from "@/components/education/education-components";

export default function ResourcesPage() {
  const [search, setSearch] = useState("");
  const [subjectFilter, setSubjectFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [page, setPage] = useState(1);

  const debouncedSearch = useDebounced(search, 320);

  const query = useMemo(() => {
    const q: Record<string, string | number | boolean | null | undefined> = { page };
    if (debouncedSearch) q.search = debouncedSearch;
    if (subjectFilter) q.subject_code = subjectFilter;
    if (categoryFilter) q.category = categoryFilter;
    return q;
  }, [debouncedSearch, subjectFilter, categoryFilter, page]);

  const { data, error, isLoading, refetch } = useResource(
    (signal) => endpoints.engagement.resources(query, { signal }),
    { deps: [JSON.stringify(query)] },
  );

  const activeFilters = (debouncedSearch ? 1 : 0) + (subjectFilter ? 1 : 0) + (categoryFilter ? 1 : 0);

  return (
    <div className="relative min-h-[calc(100dvh-4rem)]">
      <FloatingOrbs opacity={0.04} color="lilac" count={4} />
      <PageTransitionWrapper>
        <PageStack>
          <PageHeader title="Resources" description="Study materials and downloads for your subjects." />

      <FilterBar
        onReset={() => { setSearch(""); setSubjectFilter(""); setCategoryFilter(""); setPage(1); }}
        activeCount={activeFilters}
      >
        <SearchInput value={search} onChange={(v) => { setSearch(v); setPage(1); }} placeholder="Search resources…" />
        <FilterSelect
          value={subjectFilter}
          onChange={(v) => { setSubjectFilter(v); setPage(1); }}
          options={subjectOptions(data)}
          label="Subject"
          allLabel="All subjects"
        />
        <FilterSelect
          value={categoryFilter}
          onChange={(v) => { setCategoryFilter(v); setPage(1); }}
          options={categoryOptions(data)}
          label="Category"
          allLabel="All categories"
        />
      </FilterBar>

      {isLoading ? (
        <SkeletonPage />
      ) : error ? (
        <ErrorState error={error} onRetry={refetch} />
      ) : !data || data.results.length === 0 ? (
        <EmptyState
          title="No resources found"
          description={activeFilters ? "Try clearing your filters." : "No resources are available yet."}
        />
      ) : (
        <>
          <div className="space-y-3">
            {data.results.map((resource: ResourceRow) => (
              <ResourceCard key={resource.id} resource={resource} />
            ))}
          </div>
          <Pagination
            page={data.page}
            numPages={data.num_pages}
            hasNext={data.has_next}
            hasPrevious={data.has_previous}
            onChange={setPage}
            label="Resources navigation"
          />
        </>
      )}
    </PageStack>
    </PageTransitionWrapper>
    </div>
  );
}

function subjectOptions(data: Paginated<ResourceRow> | null) {
  if (!data) return [];
  const unique = new Map<string, string>();
  data.results.forEach((r) => {
    if (r.subject_code && !unique.has(r.subject_code)) unique.set(r.subject_code, r.subject_name || r.subject_code);
  });
  return Array.from(unique, ([value, label]) => ({ value, label }));
}

function categoryOptions(data: Paginated<ResourceRow> | null) {
  if (!data) return [];
  const unique = new Set<string>();
  data.results.forEach((r) => {
    if (r.category) unique.add(r.category);
  });
  return Array.from(unique).map((c) => ({ value: c, label: c }));
}

function ResourceCard({ resource }: { resource: ResourceRow }) {
  const token = subjectToken(resource.subject_color);

  return (
    <Link href={`/resources/${resource.id}`}>
      <Card className="group p-5 transition-transform hover:scale-[1.01]">
        <CardHeader>
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <CardTitle className="flex items-center gap-2">
                <span className={token.dot} />
                {resource.title}
              </CardTitle>
              <CardDescription>
                {resource.category_label} · {resource.subject_code || "General"}
              </CardDescription>
            </div>
            <Badge tone="neutral">
              {resource.category_label}
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid gap-2 text-small sm:grid-cols-2">
            {resource.file_size && (
              <div>
                <span className="text-ink-faint">Size</span>
                <span className="ml-1 font-medium text-ink">{formatFileSize(resource.file_size)}</span>
              </div>
            )}
            {resource.class_name && (
              <div>
                <span className="text-ink-faint">Class</span>
                <span className="ml-1 font-medium text-ink">{resource.class_name}</span>
              </div>
            )}
            {resource.academic_year_label && (
              <div>
                <span className="text-ink-faint">Year</span>
                <span className="ml-1 font-medium text-ink">{resource.academic_year_label}</span>
              </div>
            )}
          </div>
          {resource.description && (
            <p className="mt-2 text-small text-ink-muted">{resource.description}</p>
          )}
        </CardContent>
      </Card>
    </Link>
  );
}
