"use client";

import * as React from "react";
import { ScrollText } from "lucide-react";

import { StaffPage } from "@/components/staff/staff-page";
import { DataTable, TBody, TD, TH, THead, TR } from "@/components/ui/data-table";
import { FilterBar, FilterSelect, SearchInput } from "@/components/ui/filter-bar";
import { Badge } from "@/components/ui/badge";
import { Pagination } from "@/components/ui/tabs";
import { SkeletonList } from "@/components/ui/skeleton";
import { ErrorState, EmptyState } from "@/components/ui/states";
import { endpoints } from "@/lib/endpoints";
import { useDebounced, useResource } from "@/lib/hooks/use-resource";
import { usePagedFilters } from "@/lib/hooks/use-paged-filters";
import { formatDateTime } from "@/lib/utils";

/**
 * The audit log.
 *
 * Read only, and deliberately so: it is the record of who changed what, so it
 * has no edit affordance at all. The API exposes no mutation for it.
 */

const ROLES = [
  { value: "STUDENT", label: "Student" },
  { value: "CLASS_REPRESENTATIVE", label: "Class representative" },
  { value: "TEACHER", label: "Teacher" },
  { value: "ADMIN", label: "Administrator" },
];

/** The family of an action, for a scannable badge. */
const ACTION_TONE: Record<string, "brand" | "success" | "warning" | "info" | "neutral"> = {
  auth: "neutral",
  paper: "brand",
  result: "success",
  request: "warning",
  announcement: "info",
  event: "info",
  timetable: "brand",
  feedback: "neutral",
};

function toneFor(action: string) {
  return ACTION_TONE[action.split(".")[0]] ?? "neutral";
}

export default function StaffAuditPage() {
  const [search, setSearch] = React.useState("");
  const [role, setRole] = React.useState("");

  const debouncedSearch = useDebounced(search);
  const { page, setPage } = usePagedFilters({ search: debouncedSearch, role });

  const query = React.useMemo(
    () => ({
      search: debouncedSearch || undefined,
      role: role || undefined,
      page,
      page_size: 50,
    }),
    [debouncedSearch, role, page],
  );

  const { data, error, isLoading, refetch } = useResource(
    (signal) => endpoints.staff.auditLog(query, { signal }),
    { deps: [JSON.stringify(query)] },
  );


  const activeCount = (debouncedSearch ? 1 : 0) + (role ? 1 : 0);
  const rows = data?.results ?? [];

  return (
    <StaffPage
      capability="view_audit_log"
      eyebrow="Read only"
      title="Audit log"
      description="Every recorded action, who took it, and when."
    >
      <FilterBar
        activeCount={activeCount}
        onReset={() => {
          setSearch("");
          setRole("");
        }}
      >
        <SearchInput
          value={search}
          onChange={setSearch}
          placeholder="Search action or summary"
          className="min-w-56 flex-1"
        />
        <FilterSelect
          value={role}
          onChange={setRole}
          options={ROLES}
          label="Role"
          allLabel="All roles"
          className="w-56"
        />
      </FilterBar>

      {isLoading ? (
        <SkeletonList rows={10} />
      ) : error ? (
        <ErrorState error={error} onRetry={refetch} />
      ) : rows.length === 0 ? (
        <EmptyState
          title="No activity in this view"
          description="Recorded actions appear here as soon as they happen."
          icon={<ScrollText className="h-5 w-5" aria-hidden />}
        />
      ) : (
        <>
          <DataTable>
            <THead>
              <TR>
                <TH>When</TH>
                <TH>Actor</TH>
                <TH>Action</TH>
                <TH>Summary</TH>
                <TH>IP</TH>
              </TR>
            </THead>
            <TBody>
              {rows.map((entry) => (
                <TR key={entry.id}>
                  <TD className="whitespace-nowrap text-caption text-ink-muted">
                    {formatDateTime(entry.created_at)}
                  </TD>
                  <TD className="text-ink">
                    {entry.actor_name}
                    <span className="mt-0.5 block text-caption text-ink-faint">
                      {entry.actor_role || "—"}
                    </span>
                  </TD>
                  <TD>
                    <Badge tone={toneFor(entry.action)}>{entry.action}</Badge>
                  </TD>
                  <TD className="max-w-md text-ink-muted">{entry.summary || "—"}</TD>
                  <TD className="font-mono text-caption text-ink-faint">{entry.ip_address || "—"}</TD>
                </TR>
              ))}
            </TBody>
          </DataTable>

          <Pagination
            page={data?.page ?? 1}
            numPages={data?.num_pages ?? 1}
            hasNext={Boolean(data?.has_next)}
            hasPrevious={Boolean(data?.has_previous)}
            onChange={setPage}
            label="Audit log pages"
          />
        </>
      )}
    </StaffPage>
  );
}
