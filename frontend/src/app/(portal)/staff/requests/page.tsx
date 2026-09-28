"use client";

import * as React from "react";
import { LifeBuoy } from "lucide-react";

import { StaffPage } from "@/components/staff/staff-page";
import { DataTable, TBody, TD, TH, THead, TR } from "@/components/ui/data-table";
import { FilterBar, FilterSelect, SearchInput } from "@/components/ui/filter-bar";
import { ToneBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { Field, Textarea } from "@/components/ui/input";
import { SkeletonList } from "@/components/ui/skeleton";
import { ErrorState, EmptyState } from "@/components/ui/states";
import { Card, CardContent } from "@/components/ui/card";
import { endpoints } from "@/lib/endpoints";
import { useDebounced, useResource } from "@/lib/hooks/use-resource";
import { useRegisterTransition } from "@/lib/hooks/use-register-transition";
import { formatDate, formatDateTime, statusTone } from "@/lib/utils";
import type { LookupData, RequestStatusValue, StaffRequestRowDetail } from "@/lib/types";

/**
 * The staff request queue.
 *
 * Closing a ticket is the consequential part: the server refuses to resolve or
 * reject a request without a written response, so the dialog for those states
 * makes the response mandatory rather than discovering the rule on submit.
 */

const STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: "PENDING", label: "Pending" },
  { value: "IN_REVIEW", label: "In review" },
  { value: "RESOLVED", label: "Resolved" },
  { value: "REJECTED", label: "Rejected" },
  { value: "CLOSED", label: "Closed" },
];

const NEXT_STATUSES: Record<RequestStatusValue, RequestStatusValue[]> = {
  PENDING: ["IN_REVIEW", "RESOLVED", "REJECTED"],
  IN_REVIEW: ["RESOLVED", "REJECTED", "CLOSED"],
  RESOLVED: ["CLOSED"],
  REJECTED: ["CLOSED", "IN_REVIEW"],
  CLOSED: [],
};

/** The server requires a written response for these outcomes. */
const NEEDS_RESPONSE: RequestStatusValue[] = ["RESOLVED", "REJECTED"];

const STATUS_LABELS: Record<RequestStatusValue, string> = {
  PENDING: "Mark in review",
  IN_REVIEW: "Take it back to review",
  RESOLVED: "Resolve",
  REJECTED: "Reject",
  CLOSED: "Close",
};

export default function StaffRequestsPage() {
  const [status, setStatus] = React.useState("");
  const [classId, setClassId] = React.useState("");
  const [search, setSearch] = React.useState("");
  const debouncedSearch = useDebounced(search);
  const debouncedClass = useDebounced(classId);

  const query = React.useMemo(
    () => ({
      status: status || undefined,
      class: debouncedClass || undefined,
      search: debouncedSearch || undefined,
      limit: 100,
    }),
    [status, debouncedClass, debouncedSearch],
  );

  const { data, error, isLoading, refetch } = useResource(
    (signal) => endpoints.staff.requests(query, { signal }),
    { deps: [JSON.stringify(query)] },
  );

  const { data: lookups } = useResource<LookupData>((signal) =>
    endpoints.platform.lookups(undefined, { signal }),
  );

  const respond = useRegisterTransition({
    successTitle: "Request updated",
    run: ({ id, target, note }) => endpoints.staff.respondToRequest(id, { status: target, response: note }),
    describeSuccess: (result) => `${result.ticket_id} is now ${result.status_label.toLowerCase()}.`,
    onSettled: refetch,
  });

  const activeCount = (status ? 1 : 0) + (classId ? 1 : 0) + (search ? 1 : 0);
  const rows = data?.results ?? [];

  return (
    <StaffPage
      capability="review_requests"
      title="Request queue"
      description="Tickets raised by students, with the response they will see."
    >
      <FilterBar
        activeCount={activeCount}
        onReset={() => {
          setStatus("");
          setClassId("");
          setSearch("");
        }}
      >
        <SearchInput
          value={search}
          onChange={setSearch}
          placeholder="Search ticket, subject or student"
          className="min-w-56 flex-1"
        />
        <FilterSelect
          value={status}
          onChange={setStatus}
          options={STATUS_OPTIONS}
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
      ) : rows.length === 0 ? (
        <EmptyState
          title="No requests in this view"
          description="Tickets raised by students appear here as soon as they are submitted."
          icon={<LifeBuoy className="h-5 w-5" aria-hidden />}
        />
      ) : (
        <>
          <p className="text-caption text-ink-muted">
            {data?.open_count ?? 0} open of {data?.count ?? 0} total
          </p>
          <DataTable>
            <THead>
              <TR>
                <TH>Ticket</TH>
                <TH>Student</TH>
                <TH>Type</TH>
                <TH>Raised</TH>
                <TH>Status</TH>
                <TH>Action</TH>
              </TR>
            </THead>
            <TBody>
              {rows.map((row) => (
                <TR key={row.id}>
                  <TD className="font-medium text-ink">
                    {row.subject_line}
                    <span className="mt-0.5 block font-mono text-caption text-ink-faint">
                      {row.ticket_id}
                    </span>
                  </TD>
                  <TD className="text-ink-muted">
                    {row.student_name}
                    <span className="mt-0.5 block font-mono text-caption text-ink-faint">
                      {row.student_code}
                    </span>
                  </TD>
                  <TD className="text-ink-muted">{row.request_type_label}</TD>
                  <TD className="whitespace-nowrap text-caption text-ink-muted">
                    {formatDate(row.created_at)}
                  </TD>
                  <TD>
                    <ToneBadge tone={statusTone(row.status)}>{row.status_label}</ToneBadge>
                  </TD>
                  <TD>
                    <RespondActions
                      row={row}
                      busy={Boolean(respond.pendingKey)}
                      onRespond={(next, text) => respond.act(row.id, next, text)}
                    />
                  </TD>
                </TR>
              ))}
            </TBody>
          </DataTable>

          {rows.some((row) => row.admin_response) ? (
            <Card>
              <CardContent className="pt-4">
                <h2 className="font-display text-h3 text-ink">Your latest responses</h2>
                <div className="mt-3 space-y-3">
                  {rows
                    .filter((row) => row.admin_response)
                    .slice(0, 5)
                    .map((row) => (
                      <RequestResponse key={row.id} row={row} />
                    ))}
                </div>
              </CardContent>
            </Card>
          ) : null}
        </>
      )}
    </StaffPage>
  );
}

function RequestResponse({ row }: { row: StaffRequestRowDetail }) {
  return (
    <div className="rounded-card border border-line-soft bg-surface-muted/60 p-3.5">
      <p className="text-small font-medium text-ink">
        {row.ticket_id} · {row.student_name}
      </p>
      <p className="mt-1 text-small text-ink-muted">{row.admin_response}</p>
      <p className="mt-1 text-caption text-ink-faint">
        {row.responded_by_name}
        {row.responded_at ? ` · ${formatDateTime(row.responded_at)}` : ""}
      </p>
    </div>
  );
}

function RespondActions({
  row,
  busy,
  onRespond,
}: {
  row: StaffRequestRowDetail;
  busy: boolean;
  onRespond: (status: RequestStatusValue, response: string) => void;
}) {
  const next = NEXT_STATUSES[row.status] ?? [];

  if (next.length === 0) {
    return <span className="text-caption text-ink-faint">Closed</span>;
  }

  return (
    <div className="flex flex-wrap gap-1.5">
      {next.map((target) =>
        NEEDS_RESPONSE.includes(target) ? (
          <RespondDialog
            key={target}
            label={STATUS_LABELS[target]}
            entityLabel={row.ticket_id}
            studentName={row.student_name}
            disabled={busy}
            onConfirm={(text) => onRespond(target, text)}
          />
        ) : (
          <Button
            key={target}
            size="sm"
            variant="secondary"
            type="button"
            disabled={busy}
            onClick={() => onRespond(target, "")}
          >
            {STATUS_LABELS[target]}
          </Button>
        ),
      )}
    </div>
  );
}

function RespondDialog({
  label,
  entityLabel,
  studentName,
  disabled,
  onConfirm,
}: {
  label: string;
  entityLabel: string;
  studentName: string;
  disabled: boolean;
  onConfirm: (response: string) => void;
}) {
  const [response, setResponse] = React.useState("");

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button size="sm" variant="primary" type="button" disabled={disabled}>
          {label}
        </Button>
      </DialogTrigger>
      <DialogContent
        title={`${label} — ${entityLabel}`}
        description={`This is sent to ${studentName} as a notification. Write the outcome they will see.`}
        footer={
          <>
            <DialogClose asChild>
              <Button variant="ghost" type="button">
                Cancel
              </Button>
            </DialogClose>
            <DialogClose asChild>
              <Button
                type="button"
                disabled={response.trim().length === 0}
                onClick={() => {
                  onConfirm(response);
                  setResponse("");
                }}
              >
                {label}
              </Button>
            </DialogClose>
          </>
        }
      >
        <Field label="Response to the student" htmlFor={`response-${entityLabel}`} required>
          <Textarea
            id={`response-${entityLabel}`}
            value={response}
            onChange={(event) => setResponse(event.target.value)}
            rows={5}
            placeholder="Explain the decision or the next step…"
          />
        </Field>
      </DialogContent>
    </Dialog>
  );
}
