"use client";

import { useState } from "react";
import { Plus, Star } from "lucide-react";

import { PageHeader, PageStack } from "@/components/ui/page-header";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Badge, ToneBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field, Textarea, Select } from "@/components/ui/input";
import { RadioCard } from "@/components/ui/input";
import { SkeletonList } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { formatDate, statusTone, type Tone } from "@/lib/utils";
import { useResource, useMutation } from "@/lib/hooks/use-resource";
import { endpoints } from "@/lib/endpoints";
import type { FeedbackRow } from "@/lib/types";

const FEEDBACK_CATEGORIES = [
  { value: "bug", label: "Bug report" },
  { value: "feature", label: "Feature request" },
  { value: "general", label: "General feedback" },
  { value: "other", label: "Other" },
];

export default function FeedbackPage() {
  const [dialogOpen, setDialogOpen] = useState(false);

  const { data, error, isLoading, refetch } = useResource(
    (signal) => endpoints.engagement.feedback({ signal }),
  );

  const createMutation = useMutation(
    (body: { category: string; rating?: number | null; message: string }) =>
      endpoints.engagement.createFeedback(body),
  );

  return (
    <PageStack>
      <PageHeader
        title="Feedback"
        description="Share your suggestions and report issues."
        actions={
          <Button icon={<Plus className="h-4 w-4" />} onClick={() => setDialogOpen(true)}>
            New feedback
          </Button>
        }
      />

      <CreateFeedbackDialog
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

      {isLoading ? (
        <SkeletonList rows={4} />
      ) : error ? (
        <ErrorState error={error} onRetry={refetch} />
      ) : !data || data.results.length === 0 ? (
        <EmptyState
          title="No feedback yet"
          description="Be the first to share your feedback about the portal."
        />
      ) : (
        <div className="space-y-3">
          {data.results.map((feedback: FeedbackRow) => (
            <FeedbackCard key={feedback.id} feedback={feedback} />
          ))}
        </div>
      )}
    </PageStack>
  );
}

function FeedbackCard({ feedback }: { feedback: FeedbackRow }) {
  return (
    <Card className="p-5">
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <CardTitle>
            {FEEDBACK_CATEGORIES.find((c) => c.value === feedback.category)?.label ?? feedback.category}
          </CardTitle>
          <ToneBadge tone={feedbackStatusTone(feedback.status)}>
            {feedback.status}
          </ToneBadge>
        </div>
        <CardDescription>
          {feedback.created_at ? formatDate(feedback.created_at) : ""}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <p className="text-small text-ink-muted">{feedback.message}</p>
        {feedback.rating !== null && (
          <div className="mt-2 flex items-center gap-1">
            {Array.from({ length: 5 }).map((_, i) => (
              <Star
                key={i}
                className={`h-4 w-4 ${i < (feedback.rating ?? 0) ? "fill-warning text-warning" : "text-ink-faint/30"}`}
              />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function feedbackStatusTone(status: string): Tone {
  const s = status.toUpperCase();
  switch (s) {
    case "RESOLVED":
    case "IMPLEMENTED":
      return "success";
    case "IN_REVIEW":
      return "warning";
    case "REJECTED":
      return "danger";
    case "OPEN":
    default:
      return "info";
  }
}

function CreateFeedbackDialog({
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
  const [category, setCategory] = useState("");
  const [rating, setRating] = useState<number | null>(null);
  const [message, setMessage] = useState("");

  const submitMutation = useMutation(
    (body: { category: string; rating?: number | null; message: string }) =>
      endpoints.engagement.createFeedback(body),
  );

  async function handleSubmit() {
    if (!category || !message.trim()) return;
    const result = await submitMutation.run({ category, rating, message });
    if (result) {
      onSuccess();
      setCategory("");
      setRating(null);
      setMessage("");
    }
  }

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent
        title="New feedback"
        description="Share your suggestions, report bugs, or request features."
        size="md"
      >
        <div className="space-y-4">
          <Field label="Category" htmlFor="category" required>
            <Select
              id="category"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              required
            >
              <option value="">Select a category…</option>
              {FEEDBACK_CATEGORIES.map((cat) => (
                <option key={cat.value} value={cat.value}>{cat.label}</option>
              ))}
            </Select>
          </Field>

          <Field label="Rating (optional)" htmlFor="rating">
            <div id="rating" className="flex gap-1">
              {[1, 2, 3, 4, 5].map((star) => (
                <Star
                  key={star}
                  className={`h-6 w-6 cursor-pointer ${
                    star <= (rating ?? 0)
                      ? "fill-warning text-warning"
                      : "text-ink-faint/30 hover:text-ink-faint"
                  }`}
                  onClick={() => setRating(star)}
                />
              ))}
            </div>
          </Field>

          <Field label="Message" htmlFor="message" required>
            <Textarea
              id="message"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Tell us what's on your mind…"
              rows={4}
              required
            />
          </Field>

          {error && <p role="alert" className="text-caption text-danger">{error.message}</p>}

          <div className="flex justify-end gap-2 pt-4">
            <Button type="button" variant="secondary" onClick={onClose} disabled={isPending}>
              Cancel
            </Button>
            <Button
              variant="primary"
              loading={isPending || submitMutation.isPending}
              onClick={handleSubmit}
              disabled={!category || !message.trim()}
            >
              Submit feedback
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
