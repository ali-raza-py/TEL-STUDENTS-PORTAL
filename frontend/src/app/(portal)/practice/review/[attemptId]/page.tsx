"use client";

import { PageHeader, PageStack, SectionHeading } from "@/components/ui/page-header";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Badge, ToneBadge } from "@/components/ui/badge";
import { ProgressRing } from "@/components/ui/progress";
import { Stat } from "@/components/ui/card";
import { Skeleton, SkeletonText, SkeletonPage } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { subjectToken, formatPercent, formatMarks, statusTone } from "@/lib/utils";
import { useResource } from "@/lib/hooks/use-resource";
import { endpoints } from "@/lib/endpoints";
import type { PracticeReviewItem, PracticeResultPayload } from "@/lib/types";

export default function PracticeReviewPage({ params }: { params: { attemptId: string } }) {
  const attemptId = Number(params.attemptId);

  const { data, error, isLoading, refetch } = useResource(
    (signal) => endpoints.papers.review(attemptId, { signal }),
    { deps: [attemptId] },
  );

  if (isLoading) return <ReviewSkeleton />;
  if (error) return <ErrorState error={error} onRetry={refetch} />;
  if (!data) return null;

  return (
    <PageStack>
      <PageHeader title="Practice results" description={data.message} />

      <ResultSummary review={data.review} />

      <SectionHeading title="Question review" />
      <div className="space-y-4">
        {data.review.map((item: PracticeReviewItem) => (
          <ReviewItem key={item.question_id} item={item} />
        ))}
      </div>
    </PageStack>
  );
}

function ResultSummary({ review }: { review: PracticeReviewItem[] }) {
  const total = review.reduce((sum, item) => sum + item.marks, 0);
  const awarded = review.reduce((sum, item) => sum + item.marks_awarded, 0);
  const percentage = total > 0 ? (awarded / total) * 100 : 0;
  const correct = review.filter((i) => i.is_correct).length;
  const incorrect = review.filter((i) => i.is_correct === false).length;
  const pending = review.filter((i) => i.pending_review).length;

  return (
    <Card className="p-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <div className="text-center">
          <ProgressRing value={percentage} size={64} />
          <p className="mt-2 text-small text-ink-muted">Score</p>
        </div>
        <Stat label="Correct" value={correct} tone="success" />
        <Stat label="Incorrect" value={incorrect} tone={incorrect > 0 ? "danger" : "neutral"} />
        <Stat label="Pending review" value={pending} tone={pending > 0 ? "warning" : "neutral"} />
      </div>
      <p className="mt-4 text-center text-small text-ink-muted">
        {awarded}/{total} marks · {formatPercent(percentage, 1)}
      </p>
    </Card>
  );
}

function ReviewItem({ item }: { item: PracticeReviewItem }) {
  const answered = item.selected_option !== null;
  const statusToneValue = item.is_correct === true ? "success" : item.is_correct === false ? "danger" : "warning";

  return (
    <Card className="p-5">
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="flex items-center gap-2">
            <Badge tone="neutral" size="sm">Q{item.order}</Badge>
            <span>{item.text}</span>
          </CardTitle>
          <ToneBadge tone={statusToneValue}>
            {item.is_correct === true ? "Correct" : item.is_correct === false ? "Incorrect" : "Needs review"}
          </ToneBadge>
        </div>
      </CardHeader>

      <CardContent className="space-y-3">
        {item.question_type === "MCQ" && (
          <div className="space-y-1.5">
            {item.options.map((option, index) => {
              const isSelected = item.selected_option === index;
              const isCorrect = item.correct_option === index;
              const tone = isCorrect ? "success" : isSelected && !isCorrect ? "danger" : "neutral";
              return (
                <div
                  key={index}
                  className={`rounded-control border px-3 py-2 text-small ${toneTone(tone)}`}
                >
                  <span className="font-medium">{option}</span>
                  {isCorrect && <span className="ml-2 text-xs text-success">(Correct answer)</span>}
                  {isSelected && !isCorrect && <span className="ml-2 text-xs text-danger">(Your answer)</span>}
                </div>
              );
            })}
          </div>
        )}

        {(item.question_type === "SHORT" || item.question_type === "SUBJECTIVE") && (
          <div className="space-y-2">
            <p className="text-caption text-ink-faint">Your answer:</p>
            <p className="rounded-control bg-surface-muted/50 p-3 text-small">{item.text_answer || "—"}</p>
            {item.marks_awarded > 0 && (
              <>
                <p className="text-caption text-ink-faint">Marks awarded:</p>
                <p className="font-medium text-ink">{item.marks_awarded}/{item.marks}</p>
              </>
            )}
          </div>
        )}

        {item.explanation && (
          <div>
            <p className="text-caption text-ink-faint">Explanation</p>
            <p className="mt-1 text-small text-ink-muted">{item.explanation}</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function toneTone(tone: "success" | "danger" | "neutral"): string {
  switch (tone) {
    case "success":
      return "border-success bg-success-tint";
    case "danger":
      return "border-danger bg-danger-tint";
    default:
      return "border-line bg-surface";
  }
}

function ReviewSkeleton() {
  return (
    <PageStack>
      <PageHeader title="Practice results" description="Loading your results…" />
      <Skeleton className="h-32 w-full" />
      <div className="space-y-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <Card key={i} className="p-5">
            <SkeletonText lines={4} />
          </Card>
        ))}
      </div>
    </PageStack>
  );
}
