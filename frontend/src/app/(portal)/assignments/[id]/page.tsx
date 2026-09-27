"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Download, FileText, Send } from "lucide-react";

import { PageHeader, PageStack, SectionHeading } from "@/components/ui/page-header";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";
import { Field, Textarea } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge, ToneBadge } from "@/components/ui/badge";
import { FileUploader, useFileUploadError } from "@/components/ui/file-uploader";
import { Skeleton, SkeletonText } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { subjectToken, formatDate, statusTone, type Tone } from "@/lib/utils";
import { useResource, useMutation } from "@/lib/hooks/use-resource";
import { useAuth } from "@/components/providers/auth-provider";
import { endpoints } from "@/lib/endpoints";
import type { AssignmentRow } from "@/lib/types";

export default function AssignmentDetailPage({ params }: { params: { id: string } }) {
  const assignmentId = Number(params.id);
  const router = useRouter();
  const { user } = useAuth();

  const {
    data: pageData,
    error,
    isLoading,
    refetch,
  } = useResource(
    (signal) => endpoints.engagement.assignments({}, { signal }),
    { deps: [assignmentId] },
  );

  const submitMutation = useMutation(
    (formData: FormData) =>
      endpoints.engagement.submitAssignment(assignmentId, formData),
  );

  const [file, setFile] = useState<File | null>(null);
  const [notes, setNotes] = useState("");

  const assignment = pageData?.results?.find((a) => a.id === assignmentId);

  if (isLoading) return <AssignmentSkeleton />;
  if (error) return <ErrorState error={error} onRetry={refetch} />;
  if (!assignment) return <EmptyState title="Assignment not found" description="The assignment you're looking for doesn't exist." />;

  const token = subjectToken(assignment.subject_color);
  const canSubmit = assignment.status === "NOT_STARTED" || assignment.status === "IN_PROGRESS";
  const isSubmitted = assignment.status === "SUBMITTED" || assignment.status === "REVIEWED" || assignment.status === "LATE";
  const fileError = useFileUploadError(submitMutation.error, "attachment");

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData();
    formData.append("notes", notes);
    if (file) formData.append("attachment", file);
    const result = await submitMutation.run(formData);
    if (result !== null) {
      void refetch();
      router.refresh();
    }
  }

  return (
    <PageStack>
      <PageHeader
        title={assignment.title}
        description={
          <>
            {assignment.subject_code} — {assignment.subject_name} · Teacher: {assignment.teacher_name}
          </>
        }
      />

      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-2">
            <CardTitle className="flex items-center gap-2">
              <span className={token.dot} />
              {assignment.title}
            </CardTitle>
            <ToneBadge tone={assignmentStatusTone(assignment.status)}>
              {assignment.status.replace("_", " ")}
            </ToneBadge>
          </div>
        </CardHeader>

        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <DetailRow label="Assigned on" value={formatDate(assignment.assigned_on)} />
            <DetailRow label="Due date" value={formatDate(assignment.due_on)} />
            <DetailRow label="Max marks" value={assignment.max_marks} />
            <DetailRow label="Class" value={assignment.class_name} />
          </div>

          {assignment.attachment_url && (
            <div>
              <p className="text-caption font-semibold text-ink-faint">Attachment</p>
              <a
                href={assignment.attachment_url}
                target="_blank"
                rel="noreferrer"
                className="mt-1 flex items-center gap-2 text-small font-medium text-brand underline underline-offset-2"
              >
                <Download className="h-4 w-4" />
                {assignment.attachment_name}
              </a>
            </div>
          )}

          {assignment.description && (
            <div>
              <p className="text-caption font-semibold text-ink-faint">Description</p>
              <p className="mt-1 text-small text-ink-muted">{assignment.description}</p>
            </div>
          )}
        </CardContent>

        {isSubmitted ? (
          <CardFooter className="border-t border-line-soft">
            <div className="flex flex-col gap-2">
              <p className="text-caption text-ink-faint">Submission status</p>
              {assignment.submission?.file_url ? (
                <a
                  href={assignment.submission.file_url}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-2 text-small font-medium text-brand underline underline-offset-2"
                >
                  <FileText className="h-4 w-4" />
                  {assignment.submission.notes || "View your submitted file"}
                </a>
              ) : (
                <p className="text-small text-ink-muted">No file submitted</p>
              )}
              {assignment.submission?.marks_awarded !== null && assignment.submission?.marks_awarded !== undefined && (
                <p className="text-small">
                  <span className="text-ink-faint">Marks awarded:</span>{" "}
                  <span className="font-medium text-ink">{assignment.submission.marks_awarded}/{assignment.max_marks}</span>
                </p>
              )}
            </div>
          </CardFooter>
        ) : canSubmit ? (
          <form onSubmit={handleSubmit}>
            <CardFooter className="border-t border-line-soft">
              <div className="w-full space-y-4">
                <Field label="Your answer / notes" htmlFor="notes" hint="Add any supporting notes with your submission.">
                  <Textarea
                    id="notes"
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    placeholder="Type your answer or notes…"
                    rows={4}
                    disabled={submitMutation.isPending}
                  />
                </Field>

                <FileUploader
                  value={file}
                  onChange={setFile}
                  label="Attachment"
                  hint="PDF, image or document up to 15 MB."
                  invalid={fileError !== undefined}
                />
                {fileError && <p role="alert" className="text-caption text-danger">{fileError}</p>}

                <div className="flex justify-end">
                  <Button type="submit" loading={submitMutation.isPending} icon={<Send className="h-4 w-4" />}>
                    Submit assignment
                  </Button>
                </div>
              </div>
            </CardFooter>
          </form>
        ) : null}
      </Card>
    </PageStack>
  );
}

function DetailRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-2">
      <span className="text-caption text-ink-faint">{label}</span>
      <span className="text-small font-medium text-ink">{value}</span>
    </div>
  );
}

function assignmentStatusTone(status: string): Tone {
  const s = status.toUpperCase();
  switch (s) {
    case "SUBMITTED":
    case "REVIEWED":
      return "success";
    case "IN_PROGRESS":
      return "warning";
    case "LATE":
      return "danger";
    case "NOT_STARTED":
      return "info";
    default:
      return "neutral";
  }
}

function AssignmentSkeleton() {
  return (
    <PageStack>
      <PageHeader title="Assignment" description="Loading…" />
      <Card className="p-5">
        <SkeletonText lines={8} />
      </Card>
    </PageStack>
  );
}
