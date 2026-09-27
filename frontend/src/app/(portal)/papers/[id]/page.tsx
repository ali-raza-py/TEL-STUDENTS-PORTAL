"use client";

import Link from "next/link";
import { Download, FileText, CheckCircle, Clock, AlertCircle } from "lucide-react";

import { PageHeader, PageStack, SectionHeading } from "@/components/ui/page-header";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";
import { Badge, ToneBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Stat } from "@/components/ui/card";
import { Skeleton, SkeletonStats } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { subjectToken, formatDate, formatPercent, formatDuration } from "@/lib/utils";
import { useResource } from "@/lib/hooks/use-resource";
import { endpoints } from "@/lib/endpoints";
import type { PaperDetail } from "@/lib/types";
import { cn } from "@/lib/utils";

export default function PaperDetailPage({ params }: { params: { id: string } }) {
  const paperId = Number(params.id);

  const {
    data: paper,
    error,
    isLoading,
    refetch,
  } = useResource(
    (signal) => endpoints.papers.detail(paperId, { signal }),
    { deps: [paperId] },
  );

  if (isLoading) return <PaperSkeleton />;
  if (error) return <ErrorState error={error} onRetry={refetch} />;
  if (!paper) return null;

  const token = subjectToken(paper.subject_color);
  const isPublished = paper.status === "PUBLISHED";
  const isPracticeAvailable = paper.can_practice;

  return (
    <PageStack>
      <PageHeader
        title={paper.title}
        description={
          <>
            {paper.subject_code} — {paper.subject_name} ·{" "}
            {paper.exam_type_label} — {formatDate(paper.exam_date)}
          </>
        }
        actions={
          <div className="flex gap-2">
            {paper.paper_file_url && (
              <Button asChild variant="secondary" icon={<Download className="h-4 w-4" />}>
                <a href={paper.paper_file_url} target="_blank" rel="noreferrer">Download paper</a>
              </Button>
            )}
            {isPracticeAvailable && (
              <Button asChild variant="primary" icon={<FileText className="h-4 w-4" />}>
                <Link href={`/practice/${paper.id}`}>Start practice</Link>
              </Button>
            )}
          </div>
        }
      />

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <span className={token.dot} />
            <CardTitle>Details</CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 sm:grid-cols-2">
            <DetailRow label="Total marks" value={paper.total_marks} />
            <DetailRow label="Duration" value={`${paper.duration_minutes} minutes`} />
            <DetailRow label="Exam date" value={formatDate(paper.exam_date)} />
            <DetailRow label="Teacher" value={paper.teacher_name || "—"} />
            <DetailRow label="Class" value={paper.class_name} />
            <DetailRow label="Academic year" value={paper.academic_year_label} />
            <DetailRow
              label="Status"
              value={
                <ToneBadge tone={statusTone(paper.status)}>
                  {paper.status_label}
                </ToneBadge>
              }
            />
            <DetailRow
              label="Attempts"
              value={
                paper.attempt_count > 0
                  ? `${paper.attempt_count} attempt${paper.attempt_count > 1 ? "s" : ""}`
                  : "No attempts yet"
              }
            />
          </div>

          {paper.instructions && (
            <div className="mt-5">
              <p className="text-small font-semibold uppercase tracking-[0.07em] text-ink-faint">
                Instructions
              </p>
              <p className="mt-2 text-small text-ink-muted">{paper.instructions}</p>
            </div>
          )}

          {isPracticeAvailable && paper.attempts_remaining !== null && (
            <div className="mt-5">
              <Stat
                label="Attempts remaining"
                value={paper.attempts_remaining}
                tone={paper.attempts_remaining > 0 ? "success" : "danger"}
              />
            </div>
          )}
        </CardContent>

        {(paper.has_answer_key || isPracticeAvailable) && (
          <CardFooter className="border-t border-line-soft">
            {paper.answer_key_file_url && (
              <Button asChild variant="ghost" icon={<Download className="h-4 w-4" />}>
                <a href={paper.answer_key_file_url} target="_blank" rel="noreferrer">Download answer key</a>
              </Button>
            )}
            {isPracticeAvailable && (
              <Button asChild variant="primary" className="ml-auto" icon={<FileText className="h-4 w-4" />}>
                <Link href={`/practice/${paper.id}`}>Start practice</Link>
              </Button>
            )}
          </CardFooter>
        )}
      </Card>

      {paper.attempts.length > 0 && (
        <div className="space-y-3">
          <SectionHeading title="Attempt history" />
          <div className="space-y-2">
            {paper.attempts.map((attempt) => (
              <Card key={attempt.id} className="p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    {attemptStatusIcon(attempt.status)}
                    <span className="text-small font-medium text-ink">
                      Attempt #{attempt.attempt_number}
                    </span>
                  </div>
                  <div className="text-right">
                    {attempt.percentage !== null ? (
                      <>
                        <span className="font-medium text-ink">{attempt.score}/{attempt.total_marks}</span>
                        <span className="text-caption text-ink-muted"> {formatPercent(attempt.percentage)}</span>
                      </>
                    ) : (
                      <span className="text-caption text-ink-muted">Not graded</span>
                    )}
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </div>
      )}
    </PageStack>
  );
}

function DetailRow({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="flex justify-between gap-2">
      <span className="text-caption text-ink-faint">{label}</span>
      <span className="text-small font-medium text-ink">{value}</span>
    </div>
  );
}

function attemptStatusIcon(status: string) {
  switch (status.toLowerCase()) {
    case "completed":
    case "graded":
      return <CheckCircle className="h-4 w-4 text-success" />;
    case "in_progress":
    case "draft":
      return <Clock className="h-4 w-4 text-warning" />;
    default:
      return <AlertCircle className="h-4 w-4 text-ink-faint" />;
  }
}

function statusTone(status: string): "success" | "warning" | "danger" | "neutral" | "info" {
  const s = status.toUpperCase();
  if (s === "PUBLISHED" || s === "APPROVED") return "success";
  if (s === "PENDING" || s === "IN_PROGRESS") return "warning";
  if (s === "REJECTED" || s === "DRAFT") return "danger";
  return "neutral";
}

function PaperSkeleton() {
  return (
    <PageStack>
      <PageHeader title="Paper" description="Loading paper details…" />
      <SkeletonStats count={4} />
      <Card className="p-5">
        <Skeleton className="h-5 w-3/4" />
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-3 w-20" />
          ))}
        </div>
      </Card>
    </PageStack>
  );
}
