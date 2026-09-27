"""
Timetable submission, review and publication.

Covers the workflow rules: only the assigned representative may submit, a
submission is invisible to students until it is approved *and* published, the
review state machine refuses illegal transitions, publishing notifies the class
and archives the previous version, and a section has at most one active
representative.
"""

from __future__ import annotations

from django.db import IntegrityError, transaction
from django.utils import timezone

from academics import services
from academics.models import ClassRepresentative, Timetable, TimetableStatus, TimetableSubmission
from common.exceptions import InvalidWorkflowTransition
from common.tests.base import ApiTestCase, ServiceTestCase
from common.tests.factories import (
    build_class,
    make_admin,
    make_entries_payload,
    make_representative,
    make_student,
    make_teacher,
    make_timetable,
)
from core.models import Notification, NotificationCategory

SUBMISSION_URL = "/api/timetable/submissions/"


class TimetableSubmissionAuthorisationTests(ApiTestCase):
    def setUp(self):
        self.graph = build_class()
        self.student = make_student(self.graph, index=1)
        self.other_graph = build_class(key="B")
        self.other_rep, _, _ = make_representative(self.other_graph, index=1)
        self.rep_user, self.rep_profile, _ = make_representative(self.graph, index=9)
        self.teacher = make_teacher(campus=self.graph.campus)

    def _payload(self, **overrides):
        payload = {
            "class_id": self.graph.class_room.pk,
            "section_id": self.graph.section.pk,
            "summary": "Thursday practical moved to Lab B",
            "change_note": "Room 204 is closed for repairs.",
            "entries": make_entries_payload("CS-101", "CS-102"),
        }
        payload.update(overrides)
        return payload

    def test_a_student_who_is_not_the_representative_is_rejected(self):
        response = self.as_user(self.student.user).post(SUBMISSION_URL, self._payload(), format="json")

        self.assertEqual(response.status_code, 403, msg=response.content)
        self.assertEqual(response.json()["error"]["code"], "permission_denied")
        self.assertEqual(TimetableSubmission.objects.count(), 0)

    def test_the_assigned_representative_can_submit(self):
        response = self.as_user(self.rep_user).post(SUBMISSION_URL, self._payload(), format="json")

        self.assertEqual(response.status_code, 201, msg=response.content)
        body = response.json()
        self.assertEqual(body["status"], "SUBMITTED")
        self.assertEqual(body["entry_count"], 2)
        self.assertEqual(body["class_room"], self.graph.class_room.pk)

        submission = TimetableSubmission.objects.get()
        self.assertEqual(submission.submitted_by, self.rep_user)
        self.assertEqual(submission.class_room, self.graph.class_room)
        self.assertEqual([entry["subject_code"] for entry in submission.entries_payload],
                         ["CS-101", "CS-102"])
        self.assertTrue(submission.is_open)

    def test_a_representative_of_another_class_cannot_submit_for_this_class(self):
        response = self.as_user(self.other_rep).post(SUBMISSION_URL, self._payload(), format="json")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json()["error"]["message"], "You are not the timetable manager for this class."
        )
        self.assertEqual(TimetableSubmission.objects.count(), 0)

    def test_a_subject_the_class_does_not_offer_is_refused(self):
        response = self.as_user(self.rep_user).post(
            SUBMISSION_URL,
            self._payload(entries=make_entries_payload("BI-999")),
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("not a subject offered to this class", response.json()["error"]["message"])
        self.assertEqual(TimetableSubmission.objects.count(), 0)

    def test_only_one_open_submission_per_class_section(self):
        self.as_user(self.rep_user)
        first = self.client.post(SUBMISSION_URL, self._payload(), format="json")
        self.assertEqual(first.status_code, 201, msg=first.content)

        second = self.client.post(
            SUBMISSION_URL, self._payload(summary="A second attempt"), format="json"
        )

        self.assertEqual(second.status_code, 409)
        self.assertEqual(second.json()["error"]["code"], "invalid_workflow_transition")
        self.assertEqual(TimetableSubmission.objects.count(), 1)

    def test_a_representative_cannot_read_another_classs_submission(self):
        own = self.as_user(self.rep_user).post(SUBMISSION_URL, self._payload(), format="json")
        self.assertEqual(own.status_code, 201, msg=own.content)

        other = self.as_user(self.other_rep).post(
            SUBMISSION_URL,
            {
                "class_id": self.other_graph.class_room.pk,
                "section_id": self.other_graph.section.pk,
                "summary": "Iqbal campus assembly slot",
                "entries": make_entries_payload("CS-101"),
            },
            format="json",
        )
        self.assertEqual(other.status_code, 201, msg=other.content)
        foreign = TimetableSubmission.objects.get(class_room=self.other_graph.class_room)

        response = self.as_user(self.rep_user).get(SUBMISSION_URL)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        listed = {row["id"] for row in body["results"]}
        self.assertEqual(listed, {own.json()["id"]})
        self.assertNotIn(foreign.pk, listed)
        self.assertNotIn("Iqbal campus assembly slot", response.content.decode())

        # The other representative sees only their own, never the first class's.
        other_view = self.as_user(self.other_rep).get(SUBMISSION_URL).json()
        self.assertEqual({row["id"] for row in other_view["results"]}, {foreign.pk})

    def test_a_plain_student_sees_no_submission_queue(self):
        response = self.as_user(self.student.user).get(SUBMISSION_URL)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 0)
        self.assertEqual(
            response.json()["message"], "You are not the timetable manager for your class."
        )


class TimetableVisibilityTests(ApiTestCase):
    def setUp(self):
        self.graph = build_class()
        self.student = make_student(self.graph, index=1)
        self.rep_user, _, _ = make_representative(self.graph, index=9)
        self.teacher = make_teacher(campus=self.graph.campus)
        self.admin = make_admin()
        self.submission = self._submit()

    def _submit(self):
        response = self.as_user(self.rep_user).post(
            SUBMISSION_URL,
            {
                "class_id": self.graph.class_room.pk,
                "section_id": self.graph.section.pk,
                "summary": "Lab B for Thursday practical",
                "entries": make_entries_payload("CS-101", "CS-102"),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, msg=response.content)
        return TimetableSubmission.objects.get(pk=response.json()["id"])

    def _student_timetable(self):
        response = self.as_user(self.student.user).get("/api/timetable/")
        self.assertEqual(response.status_code, 200, msg=response.content)
        return response.json()

    def test_a_submitted_timetable_is_invisible_to_students(self):
        body = self._student_timetable()

        self.assertIsNone(body["timetable"])
        self.assertEqual(body["meta"]["message"], "Your class timetable has not been published yet.")
        self.assertEqual(
            Timetable.objects.filter(status=TimetableStatus.PUBLISHED).count(), 0
        )

    def test_an_approved_but_unpublished_timetable_is_still_invisible(self):
        response = self.as_user(self.teacher).post(
            f"{SUBMISSION_URL}{self.submission.pk}/review/",
            {"decision": "APPROVED", "note": "Approved."},
            format="json",
        )
        self.assertEqual(response.status_code, 200, msg=response.content)
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, TimetableStatus.APPROVED)

        # The materialised timetable only exists once publishing is triggered.
        self.assertEqual(Timetable.objects.count(), 0)
        self.assertIsNone(self._student_timetable()["timetable"])

    def test_the_timetable_becomes_visible_only_after_publication(self):
        self.as_user(self.teacher)
        self.client.post(
            f"{SUBMISSION_URL}{self.submission.pk}/review/",
            {"decision": "APPROVED", "note": "Approved."},
            format="json",
        )

        self.as_user(self.admin)
        publish = self.client.post(
            f"{SUBMISSION_URL}{self.submission.pk}/publish/",
            {"change_note": "Effective next week."},
            format="json",
        )
        self.assertEqual(publish.status_code, 200, msg=publish.content)

        body = self._student_timetable()
        self.assertIsNotNone(body["timetable"])
        self.assertEqual(body["timetable"]["status"], "PUBLISHED")
        self.assertEqual(body["timetable"]["version"], 1)
        self.assertEqual(len(body["timetable"]["entries"]), 2)
        self.assertEqual(
            {entry["subject_code"] for entry in body["timetable"]["entries"]},
            {"CS-101", "CS-102"},
        )
        self.assertEqual(body["timetable"]["source"], "CLASS_REPRESENTATIVE")

        versions = self.as_user(self.student.user).get("/api/timetable/versions/").json()
        self.assertEqual(versions["count"], 1)
        self.assertEqual(versions["results"][0]["status"], "PUBLISHED")

    def test_publishing_requires_an_approved_submission(self):
        response = self.as_user(self.admin).post(
            f"{SUBMISSION_URL}{self.submission.pk}/publish/", {}, format="json"
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["error"]["message"],
            "Approve the submission before publishing it to the class.",
        )
        self.assertEqual(Timetable.objects.count(), 0)
        self.assertIsNone(self._student_timetable()["timetable"])


class ReviewStateMachineTests(ServiceTestCase):
    def setUp(self):
        self.graph = build_class()
        self.admin = make_admin()
        self.teacher = make_teacher(campus=self.graph.campus)
        self.rep_user, _, _ = make_representative(self.graph, index=9)
        self.submission = services.create_submission(
            user=self.rep_user,
            class_room=self.graph.class_room,
            section=self.graph.section,
            academic_year=self.graph.academic_year,
            summary="Lab B for Thursday practical",
            change_note="",
            payload=make_entries_payload("CS-101"),
        )

    def test_a_submitted_submission_cannot_be_published_directly(self):
        self.assertEqual(self.submission.status, TimetableStatus.SUBMITTED)

        with self.assertRaises(InvalidWorkflowTransition) as caught:
            services.review_submission(
                submission=self.submission, reviewer=self.teacher, decision=TimetableStatus.PUBLISHED
            )

        self.assertIn("cannot be moved to 'PUBLISHED'", str(caught.exception))
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, TimetableStatus.SUBMITTED)
        self.assertIsNone(self.submission.reviewed_by)
        self.assertIsNone(self.submission.reviewed_at)

    def test_the_illegal_transition_is_rejected_over_the_api_with_409(self):
        response = self.as_user(self.teacher).post(
            f"{SUBMISSION_URL}{self.submission.pk}/review/",
            {"decision": "PUBLISHED"},
            format="json",
        )

        self.assertEqual(response.status_code, 409, msg=response.content)
        self.assertEqual(response.json()["error"]["code"], "invalid_workflow_transition")
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, TimetableStatus.SUBMITTED)

    def test_a_rejected_submission_cannot_be_approved(self):
        services.review_submission(
            submission=self.submission,
            reviewer=self.teacher,
            decision=TimetableStatus.REJECTED,
            note="The room booking is not confirmed.",
        )

        with self.assertRaises(InvalidWorkflowTransition):
            services.review_submission(
                submission=self.submission,
                reviewer=self.teacher,
                decision=TimetableStatus.APPROVED,
            )

        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, TimetableStatus.REJECTED)
        self.assertEqual(
            Notification.objects.get(recipient=self.rep_user).title, "Timetable submission rejected"
        )

    def test_the_legal_path_submitted_approved_published_is_accepted(self):
        services.review_submission(
            submission=self.submission, reviewer=self.teacher, decision=TimetableStatus.UNDER_REVIEW
        )
        services.review_submission(
            submission=self.submission, reviewer=self.teacher, decision=TimetableStatus.APPROVED
        )
        services.review_submission(
            submission=self.submission, reviewer=self.teacher, decision=TimetableStatus.PUBLISHED
        )

        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, TimetableStatus.PUBLISHED)


class TimetablePublicationTests(ServiceTestCase):
    def setUp(self):
        self.graph = build_class()
        self.other_graph = build_class(key="B")
        self.admin = make_admin()
        self.teacher = make_teacher(campus=self.graph.campus)
        self.rep_user, self.rep_profile, _ = make_representative(self.graph, index=9)
        self.classmate = make_student(self.graph, index=2)
        self.outsider_user, self.outsider_profile, _ = make_representative(
            self.other_graph, index=1
        )

        # A first, already published version of the class timetable.
        self.first = make_timetable(
            self.graph, version=1, status=TimetableStatus.PUBLISHED, subject_codes=("CS-101",)
        )
        self.submission = services.create_submission(
            user=self.rep_user,
            class_room=self.graph.class_room,
            section=self.graph.section,
            academic_year=self.graph.academic_year,
            summary="Lab B for Thursday practical",
            change_note="",
            payload=make_entries_payload("CS-101", "CS-102", "CS-103"),
        )
        services.review_submission(
            submission=self.submission, reviewer=self.teacher, decision=TimetableStatus.APPROVED
        )
        self.second = services.materialise_timetable_from_submission(
            submission=self.submission, publisher=self.admin
        )

    def test_publishing_archives_the_previous_published_version(self):
        self.assertEqual(self.first.status, TimetableStatus.PUBLISHED)
        self.assertEqual(self.second.status, TimetableStatus.APPROVED)

        services.publish_timetable(
            timetable=self.second, publisher=self.admin, change_note="Second issue."
        )

        self.first.refresh_from_db()
        self.second.refresh_from_db()
        self.assertEqual(self.first.status, TimetableStatus.ARCHIVED)
        self.assertIsNotNone(self.first.archived_at)
        self.assertEqual(self.second.status, TimetableStatus.PUBLISHED)
        self.assertIsNotNone(self.second.published_at)
        self.assertEqual(self.second.version, 2)
        self.assertEqual(
            Timetable.objects.filter(
                class_room=self.graph.class_room, status=TimetableStatus.PUBLISHED
            ).count(),
            1,
        )
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, TimetableStatus.PUBLISHED)

    def test_publishing_notifies_every_student_of_the_class_once(self):
        services.publish_timetable(timetable=self.second, publisher=self.admin)

        for profile in (self.rep_profile, self.classmate):
            with self.subTest(student=profile.student_code):
                notifications = Notification.objects.filter(
                    recipient=profile.user, category=NotificationCategory.TIMETABLE
                )
                self.assertGreaterEqual(notifications.count(), 1)
                titles = {row.title for row in notifications}
                self.assertIn("Your class timetable has been updated.", titles)
                self.assertIn("Timetable change", titles)
                self.assertTrue(
                    all(row.dedupe_key.endswith(":v2") or ":v2:" in row.dedupe_key for row in notifications),
                    [row.dedupe_key for row in notifications],
                )

        # No other class is notified.
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.outsider_user, category=NotificationCategory.TIMETABLE
            ).count(),
            0,
        )

    def test_republishing_is_idempotent_for_notifications(self):
        services.publish_timetable(timetable=self.second, publisher=self.admin)
        before = Notification.objects.filter(recipient=self.rep_profile.user).count()

        services.publish_timetable(timetable=self.second, publisher=self.admin)

        self.assertEqual(
            Notification.objects.filter(recipient=self.rep_profile.user).count(), before
        )

    def test_publication_is_audited(self):
        from core.models import AuditLog

        services.publish_timetable(timetable=self.second, publisher=self.admin)

        entry = AuditLog.objects.get(action="timetable.published")
        self.assertEqual(entry.actor, self.admin)
        self.assertEqual(entry.entity_type, "Timetable")
        self.assertEqual(entry.metadata["version"], 2)
        self.assertEqual(entry.metadata["entries"], 3)


class ClassRepresentativeUniquenessTests(ServiceTestCase):
    def setUp(self):
        self.graph = build_class()
        self.admin = make_admin()
        self.first_user, self.first_profile, self.first_record = make_representative(
            self.graph, index=1
        )
        self.second_profile = make_student(self.graph, index=2)

    def test_a_second_active_representative_for_the_same_section_is_refused(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ClassRepresentative.objects.create(
                    class_room=self.graph.class_room,
                    section=self.graph.section,
                    user=self.second_profile.user,
                )

        self.assertEqual(
            ClassRepresentative.objects.filter(
                class_room=self.graph.class_room, section=self.graph.section, is_active=True
            ).count(),
            1,
        )

    def test_an_inactive_representative_does_not_block_a_new_one(self):
        self.first_record.is_active = False
        self.first_record.ends_on = timezone.localdate()
        self.first_record.save(update_fields=["is_active", "ends_on"])

        second = ClassRepresentative.objects.create(
            class_room=self.graph.class_room,
            section=self.graph.section,
            user=self.second_profile.user,
        )

        self.assertTrue(second.is_active)
        self.first_record.refresh_from_db()
        self.assertFalse(self.first_record.is_active)
        self.assertIsNotNone(self.first_record.ends_on)

    def test_assigning_through_the_api_replaces_the_active_representative(self):
        response = self.as_user(self.admin).post(
            "/api/admin/class-representatives/",
            {
                "class_id": self.graph.class_room.pk,
                "section_id": self.graph.section.pk,
                "user_id": self.second_profile.user.pk,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, msg=response.content)
        self.first_record.refresh_from_db()
        self.second_profile.user.refresh_from_db()
        self.assertFalse(self.first_record.is_active)
        self.assertIsNotNone(self.first_record.ends_on)
        self.assertEqual(self.second_profile.user.role, "CLASS_REPRESENTATIVE")
        self.assertEqual(
            ClassRepresentative.objects.filter(
                class_room=self.graph.class_room, section=self.graph.section, is_active=True
            ).count(),
            1,
        )

    def test_a_representative_must_belong_to_the_selected_section(self):
        other = make_student(self.graph, index=7)
        other.class_room = None
        other.section = None
        other.save(update_fields=["class_room", "section"])

        response = self.as_user(self.admin).post(
            "/api/admin/class-representatives/",
            {
                "class_id": self.graph.class_room.pk,
                "section_id": self.graph.section.pk,
                "user_id": other.user.pk,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["error"]["message"],
            "The representative must be a student of the selected class section.",
        )
