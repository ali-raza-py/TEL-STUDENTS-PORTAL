"use client";

import { useState, useMemo } from "react";
import { Plus } from "lucide-react";

import { PageHeader, PageStack, SectionHeading } from "@/components/ui/page-header";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Badge, ToneBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Pagination } from "@/components/ui/tabs";
import { SkeletonList } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { SearchInput, FilterBar, FilterSelect } from "@/components/ui/filter-bar";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field, Input, Textarea, Select } from "@/components/ui/input";
import { FileUploader, useFileUploadError } from "@/components/ui/file-uploader";
import { formatDate, type Tone } from "@/lib/utils";
import { useResource, useMutation, useDebounced } from "@/lib/hooks/use-resource";
import { endpoints } from "@/lib/endpoints";
import type { RequestRow } from "@/lib/types";

const REQUEST_TYPES = [
  { value: "academic", label: "Academic" },
  { value: "administrative", label: "Administrative" },
  { value: "technical", label: "Technical" },
  { value: "other", label: "Other" },
];

const STATUS_OPTIONS = [
  { value: "PENDING", label: "Pending" },
  { value: "IN_REVIEW", label: "In review" },
  { value: "RESOLVED", label: "Resolved" },
  { value: "REJECTED", label: "Rejected" },
];

export default function RequestsPage() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);
  const [dialogOpen, setDialogOpen] = useState(false);

  const debouncedSearch = useDebounced(search, 320);

  const query = useMemo(() => {
    const q: Record<string, string | number | boolean | null | undefined> = { page };
    if (debouncedSearch) q.search = debouncedSearch;
    if (statusFilter) q.status = statusFilter;
    return q;
  }, [debouncedSearch, statusFilter, page]);

  const { data, error, isLoading, refetch } = useResource(
    (signal) => endpoints.engagement.requests(query, { signal }),
    { deps: [JSON.stringify(query)] },
  );

  const createMutation = useMutation(
    (form: FormData) => endpoints.engagement.createRequest(form),
  );

  const activeFilters = (debouncedSearch ? 1 : 0) + (statusFilter ? 1 : 0);

  return (
    <PageStack>
      <PageHeader
        title="Requests"
        description="Submit support tickets and track your requests."
        actions={
          <Button icon={<Plus className="h-4 w-4" />} onClick={() => setDialogOpen(true)}>
            New request
          </Button>
        }
      />

      <CreateRequestDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        isPending={createMutation.isPending}
        error={createMutation.error}
        onSuccess={() => {
          void refetch();
          setDialogOpen(false);
          createMutation.reset();
        }}
      />

      <FilterBar
        onReset={() => { setSearch(""); setStatusFilter(""); setPage(1); }}
        activeCount={activeFilters}
      >
        <SearchInput value={search} onChange={(v) => { setSearch(v); setPage(1); }} placeholder="Search requests…" />
        <FilterSelect
          value={statusFilter}
          onChange={(v) => { setStatusFilter(v); setPage(1); }}
          options={STATUS_OPTIONS}
          label="Status"
          allLabel="All statuses"
        />
      </FilterBar>

      {isLoading ? (
        <SkeletonList rows={5} />
      ) : error ? (
        <ErrorState error={error} onRetry={refetch} />
      ) : !data || data.results.length === 0 ? (
        <EmptyState
          title="No requests found"
          description={activeFilters ? "Try clearing your filters." : "You haven't submitted any requests yet."}
        />
      ) : (
        <>
          <SectionHeading title="My requests" description={`${data.count} request${data.count !== 1 ? "s" : ""}`} />
          <div className="space-y-3">
            {data.results.map((request: RequestRow) => (
              <RequestCard key={request.id} request={request} />
            ))}
          </div>
          <Pagination
            page={data.page}
            numPages={data.num_pages}
            hasNext={data.has_next}
            hasPrevious={data.has_previous}
            onChange={setPage}
            label="Requests navigation"
          />
        </>
      )}
    </PageStack>
  );
}

function RequestCard({ request }: { request: RequestRow }) {
  const statusToneValue = requestStatusTone(request.status);
  return (
    <Card className="p-5">
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <CardTitle>{request.subject_line}</CardTitle>
          <ToneBadge tone={statusToneValue}>
            {request.status_label || request.status}
          </ToneBadge>
        </div>
        <CardDescription>
          {REQUEST_TYPES.find((t) => t.value === request.request_type)?.label ?? request.request_type} ·
          Ticket #{request.ticket_id} · {formatDate(request.created_at)}
        </CardDescription>
      </CardHeader>
      {request.description && (
        <CardContent>
          <p className="line-clamp-2 text-small text-ink-muted">{request.description}</p>
        </CardContent>
      )}
      {request.admin_response && (
        <CardContent>
          <div className="rounded-control bg-surface-muted/60 p-3">
            <p className="text-caption font-semibold text-ink-faint">Response</p>
            <p className="mt-1 text-small text-ink-muted">{request.admin_response}</p>
          </div>
        </CardContent>
      )}
    </Card>
  );
}

function requestStatusTone(status: string): Tone {
  const s = status.toUpperCase();
  switch (s) {
    case "RESOLVED":
    case "CLOSED":
      return "success";
    case "IN_REVIEW":
      return "warning";
    case "PENDING":
      return "info";
    case "REJECTED":
      return "danger";
    default:
      return "neutral";
  }
}

function CreateRequestDialog({
  open,
  onClose,
  isPending,
  error,
  onSuccess,
}: {
  open: boolean;
  onClose: () => void;
  isPending: boolean;
  error: Error | null;
  onSuccess: () => void;
}) {
  const [subjectLine, setSubjectLine] = useState("");
  const [description, setDescription] = useState("");
  const [requestType, setRequestType] = useState("");
  const [relatedDate, setRelatedDate] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const fileError = useFileUploadError(error as any, "attachment");

  const submitMutation = useMutation(
    (form: FormData) => endpoints.engagement.createRequest(form),
  );

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const formData = new FormData(form);
    formData.set("subject_line", subjectLine);
    formData.set("description", description);
    formData.set("request_type", requestType);
    if (relatedDate) formData.set("related_date", relatedDate);
    if (file) formData.append("attachment", file);

    const result = await submitMutation.run(formData);
    if (result) {
      onSuccess();
      setSubjectLine("");
      setDescription("");
      setRequestType("");
      setRelatedDate("");
      setFile(null);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent
        title="New request"
        description="Submit a support ticket and our team will respond."
        size="md"
      >
        <form onSubmit={handleSubmit} className="space-y-4">
          <Field label="Request type" htmlFor="request_type" required>
            <Select
              id="request_type"
              value={requestType}
              onChange={(e) => setRequestType(e.target.value)}
              required
            >
              <option value="">Select a type…</option>
              {REQUEST_TYPES.map((type) => (
                <option key={type.value} value={type.value}>{type.label}</option>
              ))}
            </Select>
          </Field>

          <Field label="Subject" htmlFor="subject_line" required>
            <Input
              id="subject_line"
              value={subjectLine}
              onChange={(e) => setSubjectLine(e.target.value)}
              placeholder="Brief summary of your request"
              required
              disabled={isPending}
            />
          </Field>

          <Field label="Description" htmlFor="description" required>
            <Textarea
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Provide details about your request…"
              rows={4}
              required
              disabled={isPending}
            />
          </Field>

          <Field label="Related date" htmlFor="related_date">
            <Input
              id="related_date"
              type="date"
              value={relatedDate}
              onChange={(e) => setRelatedDate(e.target.value)}
              disabled={isPending}
            />
          </Field>

          <FileUploader value={file} onChange={setFile} label="Attachment" />

          {error && <p role="alert" className="text-caption text-danger">{error.message}</p>}

          <div className="flex justify-end gap-2 pt-4">
            <Button type="button" variant="secondary" onClick={onClose} disabled={isPending}>
              Cancel
            </Button>
            <Button type="submit" loading={isPending} variant="primary">
              Submit request
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
