"use client";

import { useState, useMemo } from "react";
import { Bell, CheckCheck } from "lucide-react";

import { PageHeader, PageStack, SectionHeading } from "@/components/ui/page-header";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Pagination } from "@/components/ui/tabs";
import { SkeletonList } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { Badge } from "@/components/ui/badge";
import { formatRelative, cn } from "@/lib/utils";
import { useResource, useMutation } from "@/lib/hooks/use-resource";
import { endpoints } from "@/lib/endpoints";
import type { NotificationRow } from "@/lib/types";

export default function NotificationsPage() {
  const [page, setPage] = useState(1);

  const { data, error, isLoading, refetch } = useResource(
    (signal) => endpoints.notifications.list({ page } as Record<string, string | number | boolean | null | undefined>, { signal }),
    { deps: [page] },
  );

  const markReadMutation = useMutation(
    (ids: number[]) => endpoints.notifications.markRead({ ids }),
  );

  if (isLoading) return <SkeletonList rows={8} />;
  if (error) return <ErrorState error={error} onRetry={refetch} />;
  if (!data) return null;

  const { results, unread_count } = data;
  const count = results.length;

  async function handleMarkAllRead() {
    await markReadMutation.run([]);
    void refetch();
  }

  return (
    <PageStack>
      <PageHeader
        title="Notifications"
        description={`${count} notification${count !== 1 ? "s" : ""}, ${unread_count} unread.`}
        actions={
          unread_count > 0 && (
            <Button variant="secondary" size="sm" icon={<CheckCheck className="h-4 w-4" />} onClick={handleMarkAllRead}>
              Mark all as read
            </Button>
          )
        }
      />

      {results.length === 0 ? (
        <EmptyState
          title="No notifications"
          description="You're all caught up. New notifications will appear here."
          icon={<Bell className="h-8 w-8" />}
        />
      ) : (
        <div className="space-y-3">
          {results.map((notification: NotificationRow) => (
            <NotificationCard key={notification.id} notification={notification} onRead={() => void refetch()} />
          ))}
        </div>
      )}

      {count > 0 && (
        <Pagination
          page={page}
          numPages={Math.ceil(count / 20)}
          hasNext={results.length < count}
          hasPrevious={page > 1}
          onChange={setPage}
          label="Notifications navigation"
        />
      )}
    </PageStack>
  );
}

function NotificationCard({
  notification,
  onRead,
}: {
  notification: NotificationRow;
  onRead: () => void;
}) {
  const markReadMutation = useMutation((id: number) => endpoints.notifications.markRead({ ids: [id] }));

  return (
    <Card className={cn("p-5", !notification.is_read && "border-brand bg-brand-tint/20")}>
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="flex items-center gap-2">
            <span className={cn("h-2 w-2 rounded-full", !notification.is_read ? "bg-brand" : "bg-transparent")} />
            {notification.title}
          </CardTitle>
          <Badge tone={notification.is_read ? "neutral" : "solid"}>
            {notification.is_read ? "Read" : "New"}
          </Badge>
        </div>
        <CardDescription>
          {formatRelative(notification.created_at)}
        </CardDescription>
      </CardHeader>

      {notification.body && (
        <CardContent>
          <p className="text-small text-ink-muted">{notification.body}</p>
        </CardContent>
      )}

      {notification.action_url && (
        <CardContent>
          <a
            href={notification.action_url}
            className="text-small font-medium text-brand underline underline-offset-2"
          >
            {notification.action_label || notification.action_url}
          </a>
        </CardContent>
      )}

      {!notification.is_read && (
        <CardContent>
          <Button
            variant="ghost"
            size="sm"
            onClick={async () => {
              await markReadMutation.run(notification.id);
              onRead();
            }}
            loading={markReadMutation.isPending}
          >
            Mark as read
          </Button>
        </CardContent>
      )}
    </Card>
  );
}
