"use client";

import * as React from "react";
import { FileStack } from "lucide-react";

import { StaffPage } from "@/components/staff/staff-page";
import { TransitionActions, PendingChip } from "@/components/staff/status-actions";
import { DataTable, TBody, TD, TH, THead, TR } from "@/components/ui/data-table";
import { FilterBar, FilterSelect, SearchInput } from "@/components/ui/filter-bar";
import { Badge } from "@/components/ui/badge";
import { Pagination } from "@/components/ui/tabs";
import { SkeletonList } from "@/components/ui/skeleton";
import { ErrorState, EmptyState } from "@/components/ui/states";
import { endpoints } from "@/lib/endpoints";
import { useDebounced, useResource } from "@/lib/hooks/use-resource";
import { usePagedFilters } from "@/lib/hooks/use-paged-filters";
import { useRegisterTransition } from "@/lib/hooks/use-register-transition";
import { formatDate, formatMarks, type Tone } from "@/lib/utils";
import {
  PAPER_STATUS_LABELS,
  PAPER_TRANSITIONS,
  type LookupData,
  type PaperStatus,
} from "@/lib/types";

const PAGE_SIZE = 12;

/**
 * The paper register.
 *
 * Shows the full lifecycle, not just what students can see. The action buttons
 * come from the same transition table the server enforces, so a staff member is
 * only ever offered a move the API will accept.
 */
export default function StaffPapersPage() {
  const [search, setSearch] = React.useState("");
  const [status, setStatus] = React.useState("");
  const [classId, setClassId] = React.useState("");

  const debouncedSearch = useDebounced(search);
  const { page, setPage } = usePagedFilters({
    search: debouncedSearch,
    status,
    classId,
  });

  const query = React.useMemo(
    () => ({
      search: debouncedSearch || undefined,
      status: status || undefined,
      class: classId || undefined,
      page,
      page_size: PAGE_SIZE,
    }),
    [debouncedSearch, status, classId, page],
  );

  const { data, error, isLoading, refetch } = useResource(
    (signal) => endpoints.staff.papers(query, { signal }),
    { deps: [JSON.stringify(query)] },
  );

  const { data: lookups } = useResource<LookupData>((signal) =>
    endpoints.platform.lookups(undefined, { signal }),
  );

  const { act, pendingKey } = useRegisterTransition({
    successTitle: "Paper updated",
    run: ({ id, target }) => endpoints.staff.transitionPaper(id, { status: target }),
    describeSuccess: (result) => `Moved to ${result.status_label}.`,
    onSettled: refetch,
  });

  const activeCount = (debouncedSearch ? 1 : 0) + (status ? 1 : 0) + (classId ? 1 : 0);

  return (
    <StaffPage
      capability="manage_papers"
      title="Paper register"
      description="Every paper and where it sits in the verification lifecycle."
    >
      <FilterBar
        activeCount={activeCount}
        onReset={() => {
          setSearch("");
          setStatus("");
          setClassId("");
        }}
      >
        <SearchInput
          value={search}
          onChange={setSearch}
          placeholder="Search title, subject or instructions"
          className="min-w-56 flex-1"
        />
        <FilterSelect
          value={status}
          onChange={setStatus}
          options={Object.entries(PAPER_STATUS_LABELS).map(([value, label]) => ({ value, label }))}
          label="Status"
          allLabel="All statuses"
          className="w-48"
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
      </FilterBar>

      {isLoading ? (
        <SkeletonList rows={8} />
      ) : error ? (
        <ErrorState error={error} onRetry={refetch} />
      ) : (data?.results.length ?? 0) === 0 ? (
        <EmptyState
          title="No papers match"
          description="Adjust the search or filters to widen the result."
          icon={<FileStack className="h-5 w-5" aria-hidden />}
        />
      ) : (
        <>
          <DataTable>
            <THead>
              <TR>
                <TH>Paper</TH>
                <TH>Subject</TH>
                <TH>Class</TH>
                <TH>Type</TH>
                <TH>Marks</TH>
                <TH>Exam date</TH>
                <TH>Questions</TH>
                <TH>Status</TH>
                <TH>Move to</TH>
              </TR>
            </THead>
            <TBody>
              {data?.results.map((paper) => {
                const current = paper.status as PaperStatus;
                return (
                  <TR key={paper.id}>
                    <TD className="font-medium text-ink">{paper.title}</TD>
                    <TD className="text-ink-muted">
                      {paper.subject_name}
                      <span className="ml-1.5 font-mono text-caption text-ink-faint">{paper.subject_code}</span>
                    </TD>
                    <TD className="text-ink-muted">{paper.class_name}</TD>
                    <TD className="text-ink-muted">{paper.exam_type_label}</TD>
                    <TD className="tabular-nums text-ink-muted">{formatMarks(paper.total_marks)}</TD>
                    <TD className="text-ink-muted">{formatDate(paper.exam_date)}</TD>
                    <TD className="tabular-nums text-ink-muted">{paper.question_count}</TD>
                    <TD>
                      <Badge tone={paperStatusTone(current)}>{paper.status_label}</Badge>
                    </TD>
                    <TD>
                      <TransitionActions
                        current={current}
                        transitions={PAPER_TRANSITIONS}
                        labels={PAPER_STATUS_LABELS}
                        entityLabel={paper.title}
                        noteLabel="Reason for this change"
                        confirmTargets={["ARCHIVED"]}
                        emptyHint="Final state"
                        busy={Boolean(pendingKey)}
                        onTransition={(target) => act(paper.id, target as string)}
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

          <Pagination
            page={data?.page ?? 1}
            numPages={data?.num_pages ?? 1}
            hasNext={Boolean(data?.has_next)}
            hasPrevious={Boolean(data?.has_previous)}
            onChange={setPage}
            label="Paper register pages"
          />
        </>
      )}
    </StaffPage>
  );
}

function paperStatusTone(status: PaperStatus): Tone {
  switch (status) {
    case "PUBLISHED":
    case "PRACTICE_AVAILABLE":
      return "success";
    case "VERIFIED":
      return "brand";
    case "COMPLETED":
      return "info";
    case "DRAFT":
      return "warning";
    default:
      return "neutral";
  }
}
