"use client";

import { useState } from "react";
import { CalendarDays } from "lucide-react";

import { PageHeader, PageStack } from "@/components/ui/page-header";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { Skeleton } from "@/components/ui/skeleton";
import { subjectToken, formatDate, cn } from "@/lib/utils";
import { useResource, useDebounced } from "@/lib/hooks/use-resource";
import { endpoints } from "@/lib/endpoints";
import type { CalendarResponse, AcademicEventRow } from "@/lib/types";
import { SearchInput } from "@/components/ui/filter-bar";

export default function CalendarPage() {
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebounced(search, 320);
  const year = new Date().getFullYear();
  const month = new Date().getMonth() + 1;

  const { data, error, isLoading, refetch } = useResource(
    (signal) =>
      endpoints.engagement.calendar(
        { year, month, search: debouncedSearch } as Record<string, string | number | boolean | null | undefined>,
        { signal },
      ),
    { deps: [year, month, debouncedSearch] },
  );

  if (isLoading) return <CalendarSkeleton />;
  if (error) return <ErrorState error={error} onRetry={refetch} />;
  if (!data) return null;

  const events = data.events ?? [];

  const groups: { date: string; events: AcademicEventRow[] }[] = [];
  events.forEach((event: AcademicEventRow) => {
    const dateKey = event.starts_at.slice(0, 10);
    const existing = groups.find((g) => g.date === dateKey);
    if (existing) {
      existing.events.push(event);
    } else {
      groups.push({ date: dateKey, events: [event] });
    }
  });
  groups.sort((a, b) => a.date.localeCompare(b.date));

  return (
    <PageStack>
      <PageHeader
        title="Calendar"
        description={data.range ? `${formatDate(data.range.from)} – ${formatDate(data.range.to)}` : undefined}
      />

      <SearchInput value={search} onChange={setSearch} placeholder="Search events…" className="max-w-sm" />

      {groups.length === 0 ? (
        <EmptyState
          title="No events"
          description={debouncedSearch ? "No events match your search." : "No events in this period."}
        />
      ) : (
        <div className="space-y-4">
          {groups.map((group) => (
            <div key={group.date} className="space-y-2">
              <h3 className="font-display text-h3 text-ink">{formatDate(group.date)}</h3>
              <div className="space-y-2">
                {group.events.map((event: AcademicEventRow) => {
                  const token = subjectToken(event.subject_color);
                  return (
                    <Card key={event.id} className="p-4">
                      <div className="flex items-start gap-3">
                        <CalendarDays className="mt-0.5 h-5 w-5 text-ink-faint" />
                        <div className="min-w-0 flex-1">
                          <p className="font-medium text-ink">{event.title}</p>
                          <p className="text-caption text-ink-muted">
                            {event.event_type_label} · {formatDate(event.starts_at)}
                          </p>
                          {event.description && (
                            <p className="mt-1 text-small text-ink-muted">{event.description}</p>
                          )}
                          {event.subject_name && (
                            <p className="text-caption text-ink-muted">Subject: {event.subject_name}</p>
                          )}
                        </div>
                        <span className={cn("h-3 w-3 shrink-0 rounded-full", token.dot)} />
                      </div>
                    </Card>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </PageStack>
  );
}

function CalendarSkeleton() {
  return (
    <PageStack>
      <PageHeader title="Calendar" description="Loading events…" />
      {Array.from({ length: 3 }).map((_, i) => (
        <Card key={i} className="p-4">
          <Skeleton className="h-5 w-32" />
          <Skeleton className="mt-2 h-3 w-3/4" />
          <Skeleton className="mt-1 h-3 w-1/2" />
        </Card>
      ))}
    </PageStack>
  );
}
