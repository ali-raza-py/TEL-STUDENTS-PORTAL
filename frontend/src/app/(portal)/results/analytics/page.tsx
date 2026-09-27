"use client";

import Link from "next/link";

import { PageHeader, PageStack, SectionHeading } from "@/components/ui/page-header";
import { Card, CardHeader, CardTitle, CardContent, Stat } from "@/components/ui/card";
import { Badge, ToneBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ProgressRing, BarRow } from "@/components/ui/progress";
import { Skeleton, SkeletonPage, SkeletonText, SkeletonList } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { subjectToken, formatPercent, percentageTone, type Tone, gradeTone } from "@/lib/utils";
import { useResource } from "@/lib/hooks/use-resource";
import { endpoints } from "@/lib/endpoints";
import type { TopicAnalysisResponse } from "@/lib/types";
import { cn } from "@/lib/utils";

function progressRingTone(tone: Tone): "brand" | "success" | "warning" | "danger" {
  if (tone === "info" || tone === "neutral") return "brand";
  return tone;
}

export default function AnalyticsPage() {
  const { data: analytics, error, isLoading, refetch: refetchAnalytics } = useResource(
    (signal) => endpoints.results.analytics({ signal }),
  );

  const { data: topics, error: topicsError, isLoading: topicsLoading, refetch: refetchTopics } = useResource(
    (signal) => endpoints.results.topics({}, { signal }),
  );

  if (isLoading) return <SkeletonPage />;
  if (error) return <ErrorState error={error} onRetry={refetchAnalytics} />;
  if (!analytics) return null;

  const token = (color: string | null | undefined) => subjectToken(color ?? "sage");

  return (
    <PageStack>
      <PageHeader title="Analytics" description="Your academic performance analysis." />

      {analytics.has_results ? (
        <>
          {/* Overall */}
          <Card className="p-6">
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="text-center">
                <ProgressRing
                  value={analytics.overall_average ?? 0}
                  size={72}
                  tone={progressRingTone(percentageTone(analytics.overall_average ?? 0, analytics.thresholds?.weak_subject_score ?? 50))}
                />
                <p className="mt-2 text-caption text-ink-muted">Overall average</p>
              </div>
              <Stat
                label="Weak subjects"
                value={analytics.weak_subjects.length}
                tone={analytics.weak_subjects.length > 0 ? "danger" : "success"}
              />
              <Stat
                label="Subjects tracked"
                value={analytics.subjects.length}
                tone="brand"
              />
            </div>
          </Card>

          {/* Subject performance */}
          <SectionHeading title="Subject performance" />
          <div className="space-y-3">
            {analytics.subjects.map((subject) => (
              <Card key={subject.subject_id} className="p-4">
                <BarRow
                  label={
                    <div className="flex items-center gap-2">
                      <span className={cn("h-2.5 w-2.5 rounded-full", token(subject.subject_color).dot)} />
                      <span>{subject.subject_name}</span>
                    </div>
                  }
                  value={formatPercent(subject.average_percentage)}
                  caption={`Best: ${formatPercent(subject.best_percentage)} · Assessments: ${subject.assessments}`}
                  barClassName={token(subject.subject_color).bar}
                />
              </Card>
            ))}
          </div>

          {/* Weak subjects */}
          {analytics.weak_subjects.length > 0 && (
            <>
              <SectionHeading title="Weak subjects" />
              <div className="space-y-3">
                {analytics.weak_subjects.map((ws) => (
                  <Card key={ws.subject_id} className="p-4">
                    <div className="flex items-start gap-3">
                      <span className={cn("mt-0.5 h-2.5 w-2.5 rounded-full", token(ws.subject_color).dot)} />
                      <div className="min-w-0 flex-1">
                        <p className="font-medium text-ink">{ws.subject_name}</p>
                        <BarRow
                          label="Current vs overall"
                          value={formatPercent(ws.recent_average)}
                          caption={`Overall: ${formatPercent(ws.overall_average)} · Below threshold of ${formatPercent(ws.threshold)}`}
                          barClassName={token(ws.subject_color).bar}
                        />
                        <p className="mt-2 text-caption text-ink-muted">{ws.reason}</p>
                      </div>
                      <ToneBadge tone={weakSeverityTone(ws.severity)}>{ws.severity}</ToneBadge>
                    </div>
                  </Card>
                ))}
              </div>
            </>
          )}

          {/* Topic analysis */}
          <SectionHeading
            title="Topic analysis"
            actions={
              <Link href="/results" className="text-small font-medium text-brand underline underline-offset-2">
                Back to results
              </Link>
            }
          />
          {topicsLoading ? (
            <SkeletonList rows={4} />
          ) : topicsError ? (
            <ErrorState error={topicsError} compact onRetry={refetchTopics} />
          ) : !topics || !topics.topics || topics.topics.length === 0 ? (
            <EmptyState title="No topic data available" description="Topic-level analysis is not available for your results yet." />
          ) : (
            <div className="space-y-3">
              <TopicTable topics={topics.topics} />
            </div>
          )}
        </>
      ) : (
        <EmptyState
          title="No results available"
          description={analytics.message}
        />
      )}
    </PageStack>
  );
}

function TopicTable({ topics }: { topics: TopicAnalysisResponse["topics"] }) {
  return (
    <div className="overflow-x-auto rounded-card border border-line bg-surface">
      <table className="w-full min-w-[40rem] border-collapse text-left">
        <thead className="border-b border-line bg-surface-muted/70">
          <tr>
            <th className="px-4 py-3 text-caption font-semibold uppercase text-ink-faint">Subject</th>
            <th className="px-4 py-3 text-caption font-semibold uppercase text-ink-faint">Chapter</th>
            <th className="px-4 py-3 text-caption font-semibold uppercase text-ink-faint">Topic</th>
            <th className="px-4 py-3 text-caption font-semibold uppercase text-ink-faint">Status</th>
            <th className="px-4 py-3 text-caption font-semibold uppercase text-ink-faint">% Score</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line-soft">
          {topics.map((topic, i) => {
            const tone = topic.status === "strong" ? "success" : topic.status === "steady" ? "brand" : "danger";
            return (
              <tr key={i} className="hover:bg-surface-muted/50">
                <td className="px-4 py-3.5 text-small text-ink">{topic.subject_name}</td>
                <td className="px-4 py-3.5 text-small text-ink">{topic.chapter}</td>
                <td className="px-4 py-3.5 text-small text-ink">{topic.topic}</td>
                <td className="px-4 py-3.5">
                  <ToneBadge tone={tone}>{topic.status.replace("_", " ")}</ToneBadge>
                </td>
                <td className="px-4 py-3.5 text-small font-medium text-ink">{formatPercent(topic.percentage, 1)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function weakSeverityTone(severity: string): Tone {
  switch (severity) {
    case "high": return "danger";
    case "moderate": return "warning";
    default: return "info";
  }
}

function skeleton() {}
