"use client";

import * as React from "react";
import { CalendarCheck, ExternalLink } from "lucide-react";

import { StaffPage } from "@/components/staff/staff-page";
import { DataTable, TBody, TD, TH, THead, TR } from "@/components/ui/data-table";
import { FilterBar, FilterSelect } from "@/components/ui/filter-bar";
import { ToneBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogClose, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { Field, Textarea } from "@/components/ui/input";
import { SkeletonList } from "@/components/ui/skeleton";
import { ErrorState, EmptyState } from "@/components/ui/states";
import { endpoints } from "@/lib/endpoints";
import { useAuth } from "@/components/providers/auth-provider";
import { useResource } from "@/lib/hooks/use-resource";
import { useRegisterTransition } from "@/lib/hooks/use-register-transition";
import { formatDateTime, statusTone } from "@/lib/utils";
import type { LookupData, SubmissionStatus, TimetableSubmission } from "@/lib/types";

/**
 * Timetable submission reviews.
 *
 * Review and publish are deliberately separate steps. A reviewer can approve a
 * submission or send it back, but only an administrator can make an approved
 * timetable go live. The publish control is hidden without that capability, and
 * the server refuses the call regardless — the button is affordance, not gate.
 */

const STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: "SUBMITTED", label: "Pending review" },
  { value: "UNDER_REVIEW", label: "Under review" },
  { value: "APPROVED", label: "Approved" },
  { value: "CHANGES_REQUESTED", label: "Changes requested" },
  { value: "REJECTED", label: "Rejected" },
  { value: "PUBLISHED", label: "Published" },
];

type ReviewDecision = "UNDER_REVIEW" | "APPROVED" | "CHANGES_REQUESTED" | "REJECTED";

/** Decisions offered per state, mirroring the server's ``REVIEW_TRANSITIONS``. */
const REVIEW_ACTIONS: Record<SubmissionStatus, { decision: ReviewDecision; label: string }[]> = {
  DRAFT: [],
  SUBMITTED: [
    { decision: "UNDER_REVIEW", label: "Start review" },
    { decision: "APPROVED", label: "Approve" },
    { decision: "CHANGES_REQUESTED", label: "Request changes" },
    { decision: "REJECTED", label: "Reject" },
  ],
  UNDER_REVIEW: [
    { decision: "APPROVED", label: "Approve" },
    { decision: "CHANGES_REQUESTED", label: "Request changes" },
    { decision: "REJECTED", label: "Reject" },
  ],
  CHANGES_REQUESTED: [
    { decision: "UNDER_REVIEW", label: "Resume review" },
    { decision: "APPROVED", label: "Approve" },
    { decision: "REJECTED", label: "Reject" },
  ],
  REJECTED: [],
  APPROVED: [],
  PUBLISHED: [],
  ARCHIVED: [],
};

/** A decision that sends work back must explain what to change. */
const NEEDS_NOTE: ReviewDecision[] = ["CHANGES_REQUESTED", "REJECTED"];

export default function StaffTimetableReviewsPage() {
  const { can } = useAuth();
  const [status, setStatus] = React.useState("");
  const [classId, setClassId] = React.useState("");
  const [openDetail, setOpenDetail] = React.useState<number | null>(null);

  const query = React.useMemo(
    () => ({ status: status || undefined, class: classId || undefined, limit: 100 }),
    [status, classId],
  );

  const { data, error, isLoading, refetch } = useResource(
    (signal) => endpoints.staff.timetableSubmissions(query, { signal }),
    { deps: [JSON.stringify(query)] },
  );

  const { data: lookups } = useResource<LookupData>((signal) =>
    endpoints.platform.lookups(undefined, { signal }),
  );

  const review = useRegisterTransition({
    successTitle: "Submission updated",
    run: ({ id, target, note }) => endpoints.staff.reviewSubmission(id, { decision: target, note }),
    describeSuccess: (result) => `Now ${result.status_label.toLowerCase()}.`,
    onSettled: refetch,
  });

  const publish = useRegisterTransition({
    successTitle: "Timetable published",
    run: ({ id }) => endpoints.staff.publishSubmission(id, {}),
    describeSuccess: () => "The class can now see this timetable.",
    onSettled: refetch,
  });

  const activeCount = (status ? 1 : 0) + (classId ? 1 : 0);
  const rows = data?.results ?? [];
  const detail = rows.find((row) => row.id === openDetail) ?? null;

  return (
    <StaffPage
      capability="review_timetable_submissions"
      title="Timetable reviews"
      description="Submissions from class representatives, and the decision on each."
    >
      <FilterBar
        activeCount={activeCount}
        onReset={() => {
          setStatus("");
          setClassId("");
        }}
      >
        <FilterSelect
          value={status}
          onChange={setStatus}
          options={STATUS_OPTIONS}
          label="Status"
          allLabel="All statuses"
          className="w-56"
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
        <SkeletonList rows={6} />
      ) : error ? (
        <ErrorState error={error} onRetry={refetch} />
      ) : rows.length === 0 ? (
        <EmptyState
          title="No submissions in this view"
          description="When a class representative submits a timetable change it appears here."
          icon={<CalendarCheck className="h-5 w-5" aria-hidden />}
        />
      ) : (
        <>
          <DataTable>
            <THead>
              <TR>
                <TH>Class</TH>
                <TH>Submitted by</TH>
                <TH>Summary</TH>
                <TH>Status</TH>
                <TH>Submitted</TH>
                <TH>Decision</TH>
              </TR>
            </THead>
            <TBody>
              {rows.map((row) => (
                <TR key={row.id}>
                  <TD className="font-medium text-ink">
                    {row.class_name}
                    <span className="mt-0.5 block text-caption text-ink-faint">{row.section_name}</span>
                  </TD>
                  <TD className="text-ink-muted">{row.submitted_by_name}</TD>
                  <TD className="max-w-sm text-ink-muted">
                    <span className="line-clamp-2">{row.summary || "—"}</span>
                    <button
                      type="button"
                      className="mt-1 text-caption font-medium text-brand underline underline-offset-2"
                      onClick={() => setOpenDetail(openDetail === row.id ? null : row.id)}
                    >
                      {openDetail === row.id ? "Hide detail" : "View detail"}
                    </button>
                  </TD>
                  <TD>
                    <ToneBadge tone={statusTone(row.status)}>{row.status_label}</ToneBadge>
                  </TD>
                  <TD className="whitespace-nowrap text-caption text-ink-muted">
                    {formatDateTime(row.created_at)}
                  </TD>
                  <TD>
                    <ReviewActions
                      row={row}
                      busy={Boolean(review.pendingKey) || Boolean(publish.pendingKey)}
                      canPublish={can("publish_timetable")}
                      onReview={(decision, note) => review.act(row.id, decision, note)}
                      onPublish={() => publish.act(row.id, "PUBLISHED")}
                    />
                  </TD>
                </TR>
              ))}
            </TBody>
          </DataTable>

          {detail ? <SubmissionDetail row={detail} /> : null}
        </>
      )}
    </StaffPage>
  );
}

function SubmissionDetail({ row }: { row: TimetableSubmission }) {
  return (
    <Card>
      <CardContent className="space-y-4 pt-4">
        <div>
          <p className="text-caption font-semibold uppercase tracking-[0.08em] text-ink-faint">
            Change note
          </p>
          <p className="mt-1 text-small text-ink">{row.change_note || "No change note provided."}</p>
        </div>
        {row.review_note ? (
          <div>
            <p className="text-caption font-semibold uppercase tracking-[0.08em] text-ink-faint">
              Reviewer note
            </p>
            <p className="mt-1 text-small text-ink">{row.review_note}</p>
            <p className="mt-1 text-caption text-ink-faint">
              {row.reviewed_by_name}
              {row.reviewed_at ? ` · ${formatDateTime(row.reviewed_at)}` : ""}
            </p>
          </div>
        ) : null}
        <div className="flex flex-wrap items-center gap-4 text-caption text-ink-muted">
          <span>{row.entry_count} periods proposed</span>
          {row.image_url ? (
            <a
              href={row.image_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 font-medium text-brand underline underline-offset-2"
            >
              Attached image <ExternalLink className="h-3 w-3" aria-hidden />
            </a>
          ) : null}
          {row.pdf_url ? (
            <a
              href={row.pdf_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 font-medium text-brand underline underline-offset-2"
            >
              Attached PDF <ExternalLink className="h-3 w-3" aria-hidden />
            </a>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}

function ReviewActions({
  row,
  busy,
  canPublish,
  onReview,
  onPublish,
}: {
  row: TimetableSubmission;
  busy: boolean;
  canPublish: boolean;
  onReview: (decision: ReviewDecision, note: string) => void;
  onPublish: () => void;
}) {
  const status = row.status as SubmissionStatus;
  const actions = REVIEW_ACTIONS[status] ?? [];

  if (actions.length === 0 && !(status === "APPROVED" && canPublish)) {
    return <span className="text-caption text-ink-faint">No action available</span>;
  }

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex flex-wrap gap-1.5">
        {actions.map((action) =>
          NEEDS_NOTE.includes(action.decision) ? (
            <NotedDecision
              key={action.decision}
              label={action.label}
              entityLabel={`${row.class_name} — ${row.section_name}`}
              disabled={busy}
              onConfirm={(note) => onReview(action.decision, note)}
            />
          ) : (
            <Button
              key={action.decision}
              size="sm"
              variant={action.decision === "APPROVED" ? "primary" : "secondary"}
              type="button"
              disabled={busy}
              onClick={() => onReview(action.decision, "")}
            >
              {action.label}
            </Button>
          ),
        )}
      </div>
      {status === "APPROVED" && canPublish ? (
        <PublishButton entityLabel={`${row.class_name} — ${row.section_name}`} disabled={busy} onConfirm={onPublish} />
      ) : null}
    </div>
  );
}

/** A decision that sends work back, and therefore must say what to change. */
function NotedDecision({
  label,
  entityLabel,
  disabled,
  onConfirm,
}: {
  label: string;
  entityLabel: string;
  disabled: boolean;
  onConfirm: (note: string) => void;
}) {
  const [note, setNote] = React.useState("");

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button size="sm" variant="secondary" type="button" disabled={disabled}>
          {label}
        </Button>
      </DialogTrigger>
      <DialogContent
        title={`${label} — ${entityLabel}`}
        description="Explain what needs to change so the student can act on it."
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
                disabled={note.trim().length === 0}
                onClick={() => {
                  onConfirm(note);
                  setNote("");
                }}
              >
                {label}
              </Button>
            </DialogClose>
          </>
        }
      >
        <Field label="Note to the student" htmlFor="review-note" required>
          <Textarea
            id="review-note"
            value={note}
            onChange={(event) => setNote(event.target.value)}
            rows={4}
            placeholder="What should be changed, and why…"
          />
        </Field>
      </DialogContent>
    </Dialog>
  );
}

/** Publishing creates a live timetable version, so it is confirmed explicitly. */
function PublishButton({
  entityLabel,
  disabled,
  onConfirm,
}: {
  entityLabel: string;
  disabled: boolean;
  onConfirm: () => void;
}) {
  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button size="sm" variant="primary" type="button" disabled={disabled}>
          Publish to class
        </Button>
      </DialogTrigger>
      <DialogContent
        title={`Publish timetable — ${entityLabel}`}
        description="Students see this timetable as soon as it is published. The previous version is kept."
        footer={
          <>
            <DialogClose asChild>
              <Button variant="ghost" type="button">
                Cancel
              </Button>
            </DialogClose>
            <DialogClose asChild>
              <Button type="button" onClick={onConfirm}>
                Publish
              </Button>
            </DialogClose>
          </>
        }
      >
        <p className="text-small text-ink-muted">
          This creates a new timetable version and marks it live for the class. It cannot be
          published from a state that has not been approved.
        </p>
      </DialogContent>
    </Dialog>
  );
}
