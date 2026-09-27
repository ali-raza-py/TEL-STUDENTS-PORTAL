"use client";

import { Download, ExternalLink, FileText } from "lucide-react";

import { PageHeader, PageStack } from "@/components/ui/page-header";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton, SkeletonText } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { subjectToken, formatFileSize, formatDate } from "@/lib/utils";
import { useResource } from "@/lib/hooks/use-resource";
import { endpoints } from "@/lib/endpoints";
import type { ResourceRow } from "@/lib/types";

export default function ResourceDetailPage({ params }: { params: { id: string } }) {
  const resourceId = Number(params.id);

  const {
    data: resources,
    error,
    isLoading,
    refetch,
  } = useResource(
    (signal) => endpoints.engagement.resources({}, { signal }),
    { deps: [resourceId] },
  );

  const resource = resources?.results.find((r: ResourceRow) => r.id === resourceId);

  if (isLoading) return <ResourceSkeleton />;
  if (error) return <ErrorState error={error} onRetry={refetch} />;
  if (!resource) return <EmptyState title="Resource not found" description="The requested resource doesn't exist." />;

  const token = subjectToken(resource.subject_color);

  return (
    <PageStack>
      <PageHeader title={resource.title} description={resource.category_label} />

      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-2">
            <CardTitle className="flex items-center gap-2">
              <span className={token.dot} />
              {resource.title}
            </CardTitle>
            <Badge tone="neutral">{resource.category_label}</Badge>
          </div>
          <CardDescription>
            {resource.subject_code} — {resource.subject_name} · Class: {resource.class_name}
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-4">
          {resource.description && (
            <p className="text-small text-ink-muted">{resource.description}</p>
          )}
          <div className="grid gap-2 text-small sm:grid-cols-2">
            {resource.file_size && (
              <DetailRow label="File size" value={formatFileSize(resource.file_size)} />
            )}
            {resource.content_type && (
              <DetailRow label="Type" value={resource.content_type} />
            )}
            {resource.academic_year_label && (
              <DetailRow label="Academic year" value={resource.academic_year_label} />
            )}
            {resource.published_at && (
              <DetailRow label="Published" value={formatDate(resource.published_at)} />
            )}
          </div>
        </CardContent>

        <CardFooter className="border-t border-line-soft">
          {resource.external_url ? (
            <Button asChild variant="primary" icon={<ExternalLink className="h-4 w-4" />}>
              <a href={resource.external_url} target="_blank" rel="noreferrer">Open external link</a>
            </Button>
          ) : resource.file_url ? (
            <Button asChild variant="primary" icon={<Download className="h-4 w-4" />}>
              <a href={resource.file_url} target="_blank" rel="noreferrer">Download {resource.file_name}</a>
            </Button>
          ) : (
            <p className="text-small text-ink-muted">No file available for download.</p>
          )}
        </CardFooter>
      </Card>
    </PageStack>
  );
}

function DetailRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-2">
      <span className="text-ink-faint">{label}</span>
      <span className="font-medium text-ink">{value}</span>
    </div>
  );
}

function ResourceSkeleton() {
  return (
    <PageStack>
      <PageHeader title="Resource" description="Loading…" />
      <Card className="p-5">
        <SkeletonText lines={8} />
      </Card>
    </PageStack>
  );
}
