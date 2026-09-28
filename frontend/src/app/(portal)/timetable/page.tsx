"use client";

import { PageHeader, PageStack, SectionHeading } from "@/components/ui/page-header";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge, ToneBadge } from "@/components/ui/badge";
import { Skeleton, SkeletonPage, SkeletonList } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { subjectToken, statusTone, type Tone } from "@/lib/utils";
import { useResource } from "@/lib/hooks/use-resource";
import { endpoints } from "@/lib/endpoints";
import type { TimetableResponse, TodayResponse, TimetableEntry } from "@/lib/types";
import { cn } from "@/lib/utils";
import { PageTransitionWrapper } from "@/components/education/education-components";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

export default function TimetablePage() {
  const {
    data: timetableData,
    error,
    isLoading,
    refetch,
  } = useResource((signal) => endpoints.academics.timetable({ signal }));

  const {
    data: todayData,
    error: todayError,
    isLoading: todayLoading,
    refetch: todayRefetch,
  } = useResource((signal) => endpoints.academics.today({ signal }));

  return (
    <div className="relative min-h-[calc(100dvh-4rem)]">
      <PageTransitionWrapper>
        <PageStack>
          <PageHeader
        title="My Timetable"
        description={
          timetableData?.class ? `${timetableData.class.display_name}` : undefined
        }
      />

      {/* Today preview */}
      <SectionHeading title="Today" />
      {todayLoading ? (
        <SkeletonList rows={3} />
      ) : todayError ? (
        <ErrorState error={todayError} compact onRetry={todayRefetch} />
      ) : todayData?.today && todayData.today.length > 0 ? (
        <div className="space-y-2">
          {todayData.today.map((entry) => (
            <Card key={`${entry.id}-${entry.start}`} className="p-4">
              <div className="flex items-center gap-3">
                <span className={cn("h-3 w-3 shrink-0 rounded-full", subjectToken(entry.subject_color).dot)} />
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-ink">{entry.subject}</p>
                  <p className="text-caption text-ink-muted">{entry.teacher} · {entry.room} · {entry.start_label} – {entry.end_label}</p>
                </div>
                {entry.note ? <Badge tone="neutral" size="sm">{entry.note}</Badge> : null}
              </div>
            </Card>
          ))}
        </div>
      ) : (
        <EmptyState title="No classes today" description="Enjoy your day off!" compact />
      )}

      {/* Full weekly grid */}
      <SectionHeading title="This week" />
      {isLoading ? (
        <div className="grid gap-3 sm:grid-cols-7">
          {DAYS.map((day) => (
            <div key={day} className="space-y-2">
              <Skeleton className="h-4 w-16" />
              <Skeleton className="h-6 w-full" />
              <Skeleton className="h-6 w-full" />
            </div>
          ))}
        </div>
      ) : error ? (
        <ErrorState error={error} onRetry={refetch} />
      ) : !timetableData?.timetable ? (
        <EmptyState
          title="No timetable published"
          description="Your timetable has not been published yet. Check back later."
        />
      ) : (
        <div className="grid gap-3 sm:grid-cols-7">
          {DAYS.map((day, dayIndex) => {
            const dayEntries = groupByDay(timetableData.timetable!.entries, dayIndex + 1);
            return (
              <div key={day} className="space-y-2">
                <p className="text-center text-label font-bold uppercase text-ink-faint">
                  {day.slice(0, 3)}
                </p>
                {dayEntries.length === 0 ? (
                  <p className="text-center text-caption text-ink-faint">—</p>
                ) : (
                  <div className="space-y-2">
                    {dayEntries.map((entry) => (
                      <DayEntry key={entry.id} entry={entry} />
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
      </PageStack>
      </PageTransitionWrapper>
    </div>
  );
}

function groupByDay(entries: TimetableEntry[], day: number): TimetableEntry[] {
  return entries.filter((e) => e.day_of_week === day).sort((a, b) =>
    a.start_time.localeCompare(b.start_time),
  );
}

function DayEntry({ entry }: { entry: TimetableEntry }) {
  const token = subjectToken(entry.subject_color);
  return (
    <Card className="p-3">
      <div className="flex flex-col gap-1">
        <p className="text-caption font-medium text-ink">{entry.start_label}–{entry.end_label}</p>
        <p className="text-small font-medium text-ink">{entry.subject_name}</p>
        <p className="text-caption text-ink-muted">{entry.room}</p>
      </div>
    </Card>
  );
}
