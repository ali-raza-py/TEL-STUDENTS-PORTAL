"use client";

import { PageHeader, PageStack, SectionHeading } from "@/components/ui/page-header";
import { Card, CardHeader, CardTitle, CardContent, Stat } from "@/components/ui/card";
import { Badge, ToneBadge } from "@/components/ui/badge";
import { DataTable, THead, TBody, TR, TH, TD, RowHeader } from "@/components/ui/data-table";
import { ProgressRing, BarRow } from "@/components/ui/progress";
import { Pagination } from "@/components/ui/tabs";
import { Skeleton, SkeletonPage, SkeletonList } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { SearchInput, FilterBar, FilterSelect } from "@/components/ui/filter-bar";
import { subjectToken, formatPercent, percentageTone, type Tone, formatDate, cn } from "@/lib/utils";
import { useResource, useDebounced } from "@/lib/hooks/use-resource";
import { endpoints } from "@/lib/endpoints";
import type { AttendanceSummary, AttendanceRecordRow, SubjectAttendance, Paginated } from "@/lib/types";
import { useState, useMemo } from "react";

export default function AttendancePage() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");

  const debouncedSearch = useDebounced(search, 320);

  const { data: summary, error, isLoading, refetch: refetchSummary } = useResource(
    (signal) => endpoints.attendance.summary({ signal }),
  );

  const { data: records, error: recordsError, isLoading: recordsLoading, refetch: refetchRecords } = useResource(
    (signal) => endpoints.attendance.records({ page, search: debouncedSearch } as Record<string, string | number | boolean | null | undefined>, { signal }),
    { deps: [page, debouncedSearch] },
  );

  if (isLoading) return <SkeletonPage />;
  if (error) return <ErrorState error={error} onRetry={refetchSummary} />;
  if (!summary) return null;

  return (
    <PageStack>
      <PageHeader title="Attendance" description="Your attendance overview and record history." />

      {/* Summary card */}
      <Card className="p-6">
        <div className="grid gap-6 sm:grid-cols-3">
          <div className="text-center">
          <ProgressRing
            value={summary.overall_percentage ?? 0}
            size={72}
            tone={progressRingTone(percentageTone(summary.overall_percentage ?? 0, summary.target_percentage))}
          />
            <p className="mt-2 text-caption text-ink-muted">Overall attendance</p>
          </div>
          <Stat
            label="Target"
            value={formatPercent(summary.target_percentage)}
            tone={summary.meets_target ? "success" : "warning"}
            hint={summary.meets_target ? "Target met" : "Below target"}
          />
          <Stat
            label="Total classes"
            value={(summary.total_classes ?? 0).toString()}
            tone="brand"
            hint={
              summary.counts
                ? `${formatPercent(summary.counts.present)} present, ${formatPercent(summary.counts.absent)} absent`
                : ""
            }
          />
        </div>
      </Card>

      {/* Lowest subject */}
      {summary.lowest_subject && (
        <SectionHeading
          title="Needs improvement"
          description={
            <span className="text-ink-muted">
              {summary.lowest_subject.subject_name}: {formatPercent(summary.lowest_subject.percentage)}
            </span>
          }
        />
      )}

      {/* Subject breakdown */}
      <SectionHeading title="By subject" />
      <div className="space-y-3">
        {summary.subjects.map((subject: SubjectAttendance) => {
          const token = subjectToken(subject.subject_color);
          return (
            <Card key={subject.subject_id} className="p-4">
              <BarRow
                label={
                  <div className="flex items-center gap-2">
                    <span className={cn("h-2.5 w-2.5 rounded-full", token.dot)} />
                    <span>{subject.subject_name}</span>
                  </div>
                }
                value={formatPercent(subject.percentage)}
                caption={`${subject.present} present, ${subject.absent} absent, ${subject.late} late`}
                barClassName={token.bar}
              />
            </Card>
          );
        })}
      </div>

      {/* Monthly trend */}
      {summary.monthly_trend.length > 0 && (
        <>
          <SectionHeading title="Monthly trend" />
          <div className="space-y-2">
            {summary.monthly_trend.map((month) => (
              <BarRow
                key={month.label}
                label={month.label}
                value={formatPercent(month.percentage)}
                caption={`${month.total_classes} classes`}
                barClassName="bg-brand"
              />
            ))}
          </div>
        </>
      )}

      {/* Recent records */}
      <SectionHeading title="Recent records" />
      <FilterBar onReset={() => setSearch("")} activeCount={debouncedSearch ? 1 : 0}>
        <SearchInput value={search} onChange={setSearch} placeholder="Search by subject or date…" />
      </FilterBar>

      {recordsLoading ? (
        <SkeletonList rows={5} />
      ) : recordsError ? (
        <ErrorState error={recordsError} compact onRetry={refetchRecords} />
      ) : !records || records.results.length === 0 ? (
        <EmptyState title="No attendance records found" description="Check back later." />
      ) : (
        <>
          <DataTable>
            <THead>
              <TR>
                <TH>Date</TH>
                <TH>Subject</TH>
                <TH>Status</TH>
                <TH>Period</TH>
                <TH>Note</TH>
              </TR>
            </THead>
            <TBody>
              {records.results.map((record: AttendanceRecordRow) => {
                const token = subjectToken(record.subject_color);
                return (
                  <TR key={record.id}>
                    <TD>{formatDate(record.date)}</TD>
                    <TD>
                      <div className="flex items-center gap-2">
                        <span className={cn("h-2 w-2 rounded-full", token.dot)} />
                        {record.subject_name}
                      </div>
                    </TD>
                    <TD>
                      <ToneBadge tone={statusTone(record.status)}>
                        {record.status_label}
                      </ToneBadge>
                    </TD>
                    <TD className="text-caption text-ink-muted">{record.period_label}</TD>
                    <TD className="text-caption text-ink-muted">{record.note || "—"}</TD>
                  </TR>
                );
              })}
            </TBody>
          </DataTable>
          {records && (
            <Pagination
              page={records.page}
              numPages={records.num_pages}
              hasNext={records.has_next}
              hasPrevious={records.has_previous}
              onChange={setPage}
              label="Attendance records navigation"
            />
          )}
        </>
      )}
    </PageStack>
  );
}

function statusTone(status: string): Tone {
  const s = status.toUpperCase();
   switch (s) {
    case "PRESENT": return "success";
    case "ABSENT": return "danger";
    case "LATE": return "warning";
    case "EXCUSED": return "info";
    case "ON_DUTY": return "neutral";
    default: return "neutral";
  }
}

function progressRingTone(tone: Tone): "brand" | "success" | "warning" | "danger" {
  switch (tone) {
    case "success": return "success";
    case "warning": return "warning";
    case "danger": return "danger";
    case "info": return "warning";
    default: return "brand";
  }
}
