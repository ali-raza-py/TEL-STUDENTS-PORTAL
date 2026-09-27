"use client";

import { useState, useMemo } from "react";
import Link from "next/link";

import { PageHeader, PageStack, SectionHeading } from "@/components/ui/page-header";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Badge, ToneBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Pagination } from "@/components/ui/tabs";
import { SkeletonPage, SkeletonList } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { SearchInput } from "@/components/ui/filter-bar";
import { subjectToken, formatPercent, formatDate, statusTone } from "@/lib/utils";
import { useResource, useDebounced } from "@/lib/hooks/use-resource";
import { endpoints } from "@/lib/endpoints";
import type { PaperSummary, PracticeHistoryRow, Paginated } from "@/lib/types";

export default function PracticePage() {
  const [activeTab, setActiveTab] = useState("papers");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [historyPage, setHistoryPage] = useState(1);

  const debouncedSearch = useDebounced(search, 320);

  const { data: papers, error, isLoading, refetch } = useResource(
    (signal) => endpoints.papers.list({ page, search: debouncedSearch } as Record<string, string | number | boolean | null | undefined>, { signal }),
    { deps: [page, debouncedSearch] },
  );

  const { data: history, error: historyError, isLoading: historyLoading, refetch: historyRefetch } = useResource(
    (signal) => endpoints.papers.history({ page: historyPage } as Record<string, string | number | boolean | null | undefined>, { signal }),
    { deps: [historyPage] },
  );

  const availablePapers = useMemo(
    () => papers?.results.filter((p: PaperSummary) => p.can_practice) ?? [],
    [papers?.results],
  );

  function handleSearch(value: string) {
    setSearch(value);
    setPage(1);
  }

  return (
    <PageStack>
      <PageHeader
        title="Practice"
        description="Practice with past papers and review your attempts."
      />

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="papers">Available papers</TabsTrigger>
          <TabsTrigger value="history">History</TabsTrigger>
        </TabsList>

        <TabsContent value="papers">
          <SearchInput
            value={search}
            onChange={handleSearch}
            placeholder="Search practice papers…"
            className="mb-3 max-w-sm"
          />
          {isLoading ? (
            <SkeletonPage />
          ) : error ? (
            <ErrorState error={error} onRetry={refetch} />
          ) : availablePapers.length === 0 ? (
            <EmptyState
              title="No practice papers available"
              description="Check back later for new practice opportunities."
            />
          ) : (
            <>
              <div className="space-y-3">
                {availablePapers.map((paper: PaperSummary) => {
                  const token = subjectToken(paper.subject_color);
                  return (
                    <Link key={paper.id} href={`/practice/${paper.id}`}>
                      <Card className="group p-5 transition-transform hover:scale-[1.01]">
                        <CardHeader>
                          <div className="flex items-start justify-between gap-2">
                            <div className="min-w-0">
                              <CardTitle className="flex items-center gap-2">
                                <span className={token.dot} />
                                {paper.title}
                              </CardTitle>
                              <CardDescription>
                                {paper.subject_code} — {paper.subject_name} · {paper.question_count} questions
                              </CardDescription>
                            </div>
                            <Badge tone="neutral">
                              {paper.exam_type_label}
                            </Badge>
                          </div>
                        </CardHeader>
                        <CardContent>
                          <div className="flex gap-4 text-small">
                            <span className="text-ink-muted">
                              Marks: <span className="text-ink">{paper.total_marks}</span>
                            </span>
                            <span className="text-ink-muted">
                              Time: <span className="text-ink">{paper.duration_minutes} min</span>
                            </span>
                            {paper.best_attempt_percentage !== null && (
                              <span className="text-ink-muted">
                                Best: <span className="text-ink">{formatPercent(paper.best_attempt_percentage)}</span>
                              </span>
                            )}
                          </div>
                        </CardContent>
                      </Card>
                    </Link>
                  );
                })}
              </div>
              {papers && (
                <Pagination
                  page={papers.page}
                  numPages={papers.num_pages}
                  hasNext={papers.has_next}
                  hasPrevious={papers.has_previous}
                  onChange={setPage}
                  label="Practice papers navigation"
                />
              )}
            </>
          )}
        </TabsContent>

        <TabsContent value="history">
          {historyLoading ? (
            <SkeletonList rows={6} />
          ) : historyError ? (
            <ErrorState error={historyError} onRetry={historyRefetch} />
          ) : !history || history.results.length === 0 ? (
            <EmptyState
              title="No practice attempts yet"
              description="Complete a practice paper to see your history here."
            />
          ) : (
            <>
              <div className="space-y-3">
                {history.results.map((row: PracticeHistoryRow) => {
                  const token = subjectToken(row.subject_color);
                  return (
                    <Card key={row.attempt_id} className="p-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <span className={token.dot} />
                          <div>
                            <p className="font-medium text-ink">{row.paper_title}</p>
                            <p className="text-caption text-ink-muted">
                              {row.subject_code} · {row.exam_type_label} · {formatDate(row.submitted_at)}
                            </p>
                          </div>
                        </div>
                        <div className="text-right">
                          <Badge tone={statusTone(row.status)}>
                            {row.status}
                          </Badge>
                          <p className="mt-1 text-small font-medium text-ink">
                            {row.percentage !== null ? formatPercent(row.percentage) : "—"}
                          </p>
                        </div>
                      </div>
                    </Card>
                  );
                })}
              </div>
              <Pagination
                page={history.page}
                numPages={history.num_pages}
                hasNext={history.has_next}
                hasPrevious={history.has_previous}
                onChange={setHistoryPage}
                label="Practice history navigation"
              />
            </>
          )}
        </TabsContent>
      </Tabs>
    </PageStack>
  );
}
