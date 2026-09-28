"use client";

import * as React from "react";
import { UserRoundSearch } from "lucide-react";

import { StaffPage } from "@/components/staff/staff-page";
import { DataTable, TBody, TD, TH, THead, TR } from "@/components/ui/data-table";
import { FilterBar, FilterSelect, SearchInput } from "@/components/ui/filter-bar";
import { Pagination } from "@/components/ui/tabs";
import { SkeletonList } from "@/components/ui/skeleton";
import { ErrorState, EmptyState } from "@/components/ui/states";
import { endpoints } from "@/lib/endpoints";
import { useDebounced, useResource } from "@/lib/hooks/use-resource";
import { usePagedFilters } from "@/lib/hooks/use-paged-filters";
import type { LookupData } from "@/lib/types";

const PAGE_SIZE = 50;

/**
 * The student register.
 *
 * Reads `/api/manage/students/`, which the server already scopes to the
 * caller's campus for teachers. The class filter is sent to the server rather
 * than applied locally, so the count always describes the filtered result.
 */
export default function StaffStudentsPage() {
  const [search, setSearch] = React.useState("");
  const [classId, setClassId] = React.useState("");

  const debouncedSearch = useDebounced(search);
  const { page, setPage } = usePagedFilters({ search: debouncedSearch, classId });

  const query = React.useMemo(
    () => ({
      search: debouncedSearch || undefined,
      class: classId || undefined,
      limit: PAGE_SIZE,
      offset: (page - 1) * PAGE_SIZE,
    }),
    [debouncedSearch, classId, page],
  );

  const { data, error, isLoading, refetch } = useResource(
    (signal) => endpoints.staff.students(query, { signal }),
    { deps: [JSON.stringify(query)] },
  );

  const { data: lookups } = useResource<LookupData>((signal) =>
    endpoints.platform.lookups(undefined, { signal }),
  );

  const classOptions = (lookups?.classes ?? []).map((row) => ({
    value: String(row.id),
    label: row.display_name || row.name,
  }));

  return (
    <StaffPage
      capability="view_students"
      title="Students"
      description="Everyone on the register, scoped to what your role may see."
    >
      <FilterBar
        activeCount={(debouncedSearch ? 1 : 0) + (classId ? 1 : 0)}
        onReset={() => {
          setSearch("");
          setClassId("");
        }}
      >
        <SearchInput
          value={search}
          onChange={setSearch}
          placeholder="Search by name or student code"
          className="min-w-56 flex-1"
        />
        <FilterSelect
          value={classId}
          onChange={setClassId}
          options={classOptions}
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
          title="No students match"
          description="Adjust the search or class filter to widen the result."
          icon={<UserRoundSearch className="h-5 w-5" aria-hidden />}
        />
      ) : (
        <>
          <DataTable>
            <THead>
              <TR>
                <TH>Student</TH>
                <TH>Code</TH>
                <TH>Class</TH>
                <TH>Section</TH>
              </TR>
            </THead>
            <TBody>
              {data?.results.map((row) => (
                <TR key={row.id}>
                  <TD className="font-medium text-ink">{row.name}</TD>
                  <TD className="font-mono text-caption text-ink-muted">{row.student_code}</TD>
                  <TD className="text-ink-muted">{row.class_name || "—"}</TD>
                  <TD className="text-ink-muted">{row.section_name || "—"}</TD>
                </TR>
              ))}
            </TBody>
          </DataTable>

          <Pagination
            page={page}
            numPages={Math.max(1, Math.ceil((data?.count ?? 0) / PAGE_SIZE))}
            hasNext={page * PAGE_SIZE < (data?.count ?? 0)}
            hasPrevious={page > 1}
            onChange={setPage}
            label="Student register pages"
          />
          <p className="text-caption text-ink-faint">
            Showing {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, data?.count ?? 0)} of{" "}
            {data?.count ?? 0} students
          </p>
        </>
      )}
    </StaffPage>
  );
}
