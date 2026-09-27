"use client";

import { Download } from "lucide-react";

import { PageHeader, PageStack } from "@/components/ui/page-header";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton, SkeletonText } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { formatDate, formatRelative } from "@/lib/utils";
import { useResource } from "@/lib/hooks/use-resource";
import { endpoints } from "@/lib/endpoints";
import type { AnnouncementRow } from "@/lib/types";

export default function AnnouncementDetailPage({ params }: { params: { id: string } }) {
  const announcementId = Number(params.id);

  const { data, error, isLoading, refetch } = useResource(
    (signal) => endpoints.engagement.announcements({}, { signal }),
    { deps: [announcementId] },
  );

  const announcement = data?.results.find((a: AnnouncementRow) => a.id === announcementId);

  if (isLoading) return <AnnouncementSkeleton />;
  if (error) return <ErrorState error={error} onRetry={refetch} />;
  if (!announcement) return <EmptyState title="Announcement not found" description="The announcement you're looking for doesn't exist." />;

  const audienceParts = [
    announcement.campus_name,
    announcement.program_name,
    announcement.class_name,
    announcement.section_name,
    announcement.academic_year_label,
  ].filter(Boolean);

  return (
    <PageStack>
      <PageHeader
        title={announcement.title}
        description={
          <>
            By {announcement.author_name} ·{" "}
            {formatDate(announcement.published_at)} ({formatRelative(announcement.published_at)})
          </>
        }
        actions={
          <Badge tone="neutral" className={announcement.is_pinned ? "border-brand text-brand" : ""}>
            {announcement.is_pinned ? "Pinned" : "Announcement"}
          </Badge>
        }
      />

      <Card>
        <CardHeader>
          <CardTitle>{announcement.title}</CardTitle>
          <CardDescription>
            Audience: {audienceParts.length > 0 ? audienceParts.join(" · ") : "All"}
          </CardDescription>
        </CardHeader>

        <CardContent>
          <p className="whitespace-pre-line text-small text-ink">{announcement.body}</p>
        </CardContent>

        {announcement.attachment_url && (
          <CardFooter className="border-t border-line-soft">
            <a
              href={announcement.attachment_url}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-2 text-small font-medium text-brand underline underline-offset-2"
            >
              <Download className="h-4 w-4" />
              {announcement.attachment_name}
            </a>
          </CardFooter>
        )}
      </Card>
    </PageStack>
  );
}

function AnnouncementSkeleton() {
  return (
    <PageStack>
      <PageHeader title="Announcement" description="Loading…" />
      <Card className="p-5">
        <SkeletonText lines={12} />
      </Card>
    </PageStack>
  );
}
