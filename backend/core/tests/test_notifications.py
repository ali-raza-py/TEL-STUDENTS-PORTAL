"""Notification delivery: deduplication, visibility and the read state."""

from __future__ import annotations

from django.db import IntegrityError, transaction
from django.utils import timezone

from common.tests.base import ApiTestCase, ServiceTestCase
from common.tests.factories import build_class, make_student
from core.models import Notification, NotificationState
from core.notifications import notify


def make_notification(user, *, dedupe_key="", category="GENERAL", title="Hello", body="Body"):
    return notify(
        recipient=user, category=category, title=title, body=body, dedupe_key=dedupe_key
    )


class NotifyDedupeTests(ServiceTestCase):
    def setUp(self):
        self.graph = build_class()
        self.profile = make_student(self.graph, index=1)
        self.other = make_student(self.graph, index=2)

    def test_the_same_dedupe_key_for_one_recipient_yields_one_row(self):
        first = make_notification(self.profile.user, dedupe_key="result-published:1")
        second = make_notification(self.profile.user, dedupe_key="result-published:1")

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(
            Notification.objects.filter(recipient=self.profile.user).count(), 1
        )

    def test_deduplication_is_scoped_to_the_recipient(self):
        mine = make_notification(self.profile.user, dedupe_key="shared-key")
        theirs = make_notification(self.other.user, dedupe_key="shared-key")

        self.assertNotEqual(mine.pk, theirs.pk)
        self.assertEqual(Notification.objects.count(), 2)
        self.assertEqual(
            Notification.objects.filter(dedupe_key="shared-key").count(), 2
        )

    def test_notifications_without_a_dedupe_key_are_never_merged(self):
        first = make_notification(self.profile.user, dedupe_key="")
        second = make_notification(self.profile.user, dedupe_key="")

        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(Notification.objects.filter(recipient=self.profile.user).count(), 2)

    def test_the_database_refuses_a_duplicate_key_for_one_recipient(self):
        make_notification(self.profile.user, dedupe_key="unique-key")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Notification.objects.create(
                    recipient=self.profile.user,
                    category="GENERAL",
                    title="Duplicate",
                    body="",
                    dedupe_key="unique-key",
                )

        self.assertEqual(Notification.objects.count(), 1)

    def test_a_new_notification_starts_unread(self):
        notification = make_notification(self.profile.user, dedupe_key="k")

        self.assertEqual(notification.state, NotificationState.UNREAD)
        self.assertIsNone(notification.read_at)
        self.assertIsNotNone(notification.created_at)


class NotificationApiTests(ApiTestCase):
    def setUp(self):
        self.graph = build_class()
        self.profile = make_student(self.graph, index=1)
        self.other = make_student(self.graph, index=2)
        self.first = make_notification(
            self.profile.user, dedupe_key="n1", title="Timetable published"
        )
        self.second = make_notification(
            self.profile.user, dedupe_key="n2", title="Result published", category="RESULT"
        )
        self.foreign = make_notification(self.other.user, dedupe_key="n1")

    def test_the_inbox_only_lists_the_recipients_own_notifications(self):
        body = self.as_user(self.profile.user).get("/api/notifications/").json()

        self.assertEqual(len(body["results"]), 2)
        self.assertEqual(
            {row["title"] for row in body["results"]},
            {"Timetable published", "Result published"},
        )
        self.assertTrue(all(row["is_read"] is False for row in body["results"]))
        self.assertEqual(body["unread_count"], 2)
        self.assertNotIn(self.foreign.pk, [row["id"] for row in body["results"]])

    def test_marking_all_read_sets_the_state_and_the_timestamp(self):
        response = self.as_user(self.profile.user).post(
            "/api/notifications/", {"all": True}, format="json"
        )

        self.assertEqual(response.status_code, 200, msg=response.content)
        self.assertEqual(response.json()["marked"], 2)

        self.first.refresh_from_db()
        self.second.refresh_from_db()
        for notification in (self.first, self.second):
            with self.subTest(notification=notification.pk):
                self.assertEqual(notification.state, NotificationState.READ)
                self.assertIsNotNone(notification.read_at)
                self.assertLessEqual(notification.read_at, timezone.now())

        # Somebody else's notification is untouched.
        self.foreign.refresh_from_db()
        self.assertEqual(self.foreign.state, NotificationState.UNREAD)
        self.assertIsNone(self.foreign.read_at)

        body = self.as_user(self.profile.user).get("/api/notifications/").json()
        self.assertEqual(body["unread_count"], 0)
        self.assertTrue(all(row["is_read"] for row in body["results"]))
        self.assertIsNotNone(body["results"][0]["read_at"])

    def test_marking_a_selection_read_leaves_the_others_unread(self):
        response = self.as_user(self.profile.user).post(
            "/api/notifications/", {"ids": [self.first.pk]}, format="json"
        )

        self.assertEqual(response.status_code, 200, msg=response.content)
        self.assertEqual(response.json()["marked"], 1)

        self.first.refresh_from_db()
        self.second.refresh_from_db()
        self.assertEqual(self.first.state, NotificationState.READ)
        self.assertIsNotNone(self.first.read_at)
        self.assertEqual(self.second.state, NotificationState.UNREAD)
        self.assertIsNone(self.second.read_at)

        body = self.as_user(self.profile.user).get("/api/notifications/").json()
        self.assertEqual(body["unread_count"], 1)

    def test_marking_a_selection_never_reaches_another_recipient(self):
        response = self.as_user(self.profile.user).post(
            "/api/notifications/", {"ids": [self.foreign.pk]}, format="json"
        )

        self.assertEqual(response.status_code, 200, msg=response.content)
        self.assertEqual(response.json()["marked"], 0)
        self.foreign.refresh_from_db()
        self.assertEqual(self.foreign.state, NotificationState.UNREAD)
        self.assertIsNone(self.foreign.read_at)

    def test_marking_nothing_is_rejected(self):
        response = self.as_user(self.profile.user).post(
            "/api/notifications/", {}, format="json"
        )

        self.assertEqual(response.status_code, 400, msg=response.content)
        self.first.refresh_from_db()
        self.assertEqual(self.first.state, NotificationState.UNREAD)

    def test_unread_count_ignores_notifications_of_others(self):
        body = self.as_user(self.profile.user).get("/api/notifications/?state=unread").json()

        self.assertEqual(len(body["results"]), 2)
        self.assertEqual(body["unread_count"], 2)

    def test_archived_notifications_are_hidden_from_the_inbox(self):
        Notification.objects.filter(pk=self.first.pk).update(is_archived=True)

        body = self.as_user(self.profile.user).get("/api/notifications/").json()

        self.assertEqual([row["id"] for row in body["results"]], [self.second.pk])
        self.assertEqual(body["unread_count"], 1)

    def test_the_unread_counter_endpoint_matches_the_inbox(self):
        counter = self.as_user(self.profile.user).get("/api/notifications/unread-count/").json()
        self.assertEqual(counter["unread_count"], 2)

        self.as_user(self.profile.user).post("/api/notifications/", {"all": True}, format="json")

        counter = self.as_user(self.profile.user).get("/api/notifications/unread-count/").json()
        self.assertEqual(counter["unread_count"], 0)
