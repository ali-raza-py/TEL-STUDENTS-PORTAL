"use client";

import * as React from "react";
import { GraduationCap } from "lucide-react";

import { StaffPage } from "@/components/staff/staff-page";
import { TransitionActions, PendingChip } from "@/components/staff/status-actions";
import { DataTable, TBody, TD, TH, THead, TR } from "@/components/ui/data-table";
import { FilterBar, FilterSelect, SearchInput } from "@/components/ui/filter-bar";
import { Badge } from "@/components/ui/badge";
import { SkeletonList } from "@/components/ui/skeleton";
import { ErrorState, EmptyState } from "@/components/ui/states";
import { endpoints } from "@/lib/endpoints";
import { useDebounced, useResource } from "@/lib/hooks/use-resource";
import { useRegisterTransition } from "@/lib/hooks/use-register-transition";
import { formatDate, formatMarks, percentageTone } from "@/lib/utils";
import {
  RESULT_STATUS_LABELS,
  RESULT_TRANSITIONS,
  type LookupData,
  type ResultStatusValue,
} from "@/lib/types";

const LIMIT = 50;

/**
 * The result register.
 *
 * Publishing is the consequential move here — a published result is visible to
 * the student — so it is confirmed and asks for a note. The student name comes
 * from the server, not from a client-side join, so a row always identifies who
 * it belongs to.
 */
export default function StaffResultsPage() {
  const [status, setStatus] = React.useState("");
  const [classId, setClassId] = React.useState("");
  const [subjectId, setSubjectId] = React.useState("");
  const [search, setSearch] = React.useState("");
  const debouncedSearch = useDebounced(search);
  const debouncedClass = useDebounced(classId);
  const debouncedSubject = useDebounced(subjectId);

  const query = React.useMemo(
    () => ({
      status: status || undefined,
      class: debouncedClass || undefined,
      subject: debouncedSubject || undefined,
      search: debouncedSearch || undefined,
      limit: LIMIT,
    }),
    [status, debouncedClass, debouncedSubject, debouncedSearch],
  );

  const { data, error, isLoading, refetch } = useResource(
    (signal) => endpoints.staff.results(query, { signal }),
    { deps: [JSON.stringify(query)] },
  );

  const { data: lookups } = useResource<LookupData>((signal) =>
    endpoints.platform.lookups(undefined, { signal }),
  );

  const { act, pendingKey } = useRegisterTransition({
    successTitle: "Result updated",
    run: ({ id, target, note }) =>
      endpoints.staff.transitionResult(id, { status: target, note }),
    describeSuccess: (result) => `Now ${result.status_label.toLowerCase()}.`,
    onSettled: refetch,
  });

  const rows = data?.results ?? [];

  const activeCount =
    (status ? 1 : 0) + (classId ? 1 : 0) + (subjectId ? 1 : 0) + (search ? 1 : 0);

  return (
    <StaffPage
      capability="manage_results"
      title="Result register"
      description="Every recorded result and where it sits before students can see it."
    >
      <FilterBar
        activeCount={activeCount}
        onReset={() => {
          setStatus("");
          setClassId("");
          setSubjectId("");
        }}
      >
        <FilterSelect
          value={status}
          onChange={setStatus}
          options={Object.entries(RESULT_STATUS_LABELS).map(([value, label]) => ({ value, label }))}
          label="Status"
          allLabel="All statuses"
          className="w-48"
        />
        <SearchInput
          value={search}
          onChange={setSearch}
          placeholder="Search student, code or assessment"
          className="min-w-56 flex-1"
        />
        <FilterSelect
          value={classId}
          onChange={setClassId}
          options={(lookups?.classes ?? []).map((row) => ({
            value: String(row.id),
            label: row.display_name || row.name,
          }))}
          label="Class"
          allLabel="All classes"
          className="w-64"
        />
        <FilterSelect
          value={subjectId}
          onChange={setSubjectId}
          options={(lookups?.subjects ?? []).map((row) => ({ value: String(row.id), label: row.name }))}
          label="Subject"
          allLabel="All subjects"
          className="w-56"
        />
      </FilterBar>

      {isLoading ? (
        <SkeletonList rows={10} />
      ) : error ? (
        <ErrorState error={error} onRetry={refetch} />
      ) : rows.length === 0 ? (
        <EmptyState
          title="No results match"
          description="Adjust the filters to widen the result."
          icon={<GraduationCap className="h-5 w-5" aria-hidden />}
        />
      ) : (
        <>
          <DataTable>
            <THead>
              <TR>
                <TH>Student</TH>
                <TH>Assessment</TH>
                <TH>Subject</TH>
                <TH>Date</TH>
                <TH>Marks</TH>
                <TH>Score</TH>
                <TH>Grade</TH>
                <TH>Status</TH>
                <TH>Move to</TH>
              </TR>
            </THead>
            <TBody>
              {rows.map((row) => {
                const current = row.status as ResultStatusValue;
                return (
                  <TR key={row.id}>
                    <TD className="font-medium text-ink">
                      {row.student_name || "Unknown student"}
                      <span className="mt-0.5 block font-mono text-caption text-ink-faint">
                        {row.student_code}
                      </span>
                    </TD>
                    <TD className="text-ink-muted">{row.assessment_name}</TD>
                    <TD className="text-ink-muted">{row.subject_name}</TD>
                    <TD className="text-ink-muted">{formatDate(row.assessment_date)}</TD>
                    <TD className="tabular-nums text-ink-muted">
                      {formatMarks(row.obtained_marks)}/{formatMarks(row.total_marks)}
                    </TD>
                    <TD>
                      <Badge tone={percentageTone(row.percentage, 50)}>{row.percentage.toFixed(1)}%</Badge>
                    </TD>
                    <TD className="font-medium text-ink">{row.grade || "—"}</TD>
                    <TD>
                      <Badge tone={resultStatusTone(current)}>{row.status_label}</Badge>
                    </TD>
                    <TD>
                      <TransitionActions
                        current={current}
                        transitions={RESULT_TRANSITIONS}
                        labels={RESULT_STATUS_LABELS}
                        entityLabel={`${row.student_name} — ${row.assessment_name}`}
                        noteLabel="Reason for this change"
                        noteRequired
                        confirmTargets={["PUBLISHED", "VERIFIED"]}
                        emptyHint="Final state"
                        busy={Boolean(pendingKey)}
                        onTransition={(target, note) => act(row.id, target as string, note)}
                      />
                    </TD>
                  </TR>
                );
              })}
            </TBody>
          </DataTable>

          {pendingKey ? (
            <div className="pt-1">
              <PendingChip label="Saving change…" />
            </div>
          ) : null}

          <p className="text-caption text-ink-faint">
            Showing {rows.length} of {data?.count ?? 0} results
            {data && data.count > rows.length
              ? ` · refine the filters to narrow ${data.count} matches`
              : ""}
          </p>
        </>
      )}
    </StaffPage>
  );
}

function resultStatusTone(status: ResultStatusValue) {
  switch (status) {
    case "PUBLISHED":
      return "success" as const;
    case "VERIFIED":
      return "brand" as const;
    case "SUBMITTED":
      return "info" as const;
    default:
      return "warning" as const;
  }
}
