"""
Upload hardening: extension allow-list, content sniffing, size cap and
non-guessable storage keys. The API level tests also prove that a stored file is
only reachable through the authorised file view.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from contextlib import contextmanager
from pathlib import PurePosixPath

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APIClient

from common.tests.base import ApiTestCase, ServiceTestCase
from common.tests.factories import build_class, make_student, make_teacher
from common.uploads import validate_upload
from core.models import UploadRecord

PDF_BYTES = b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n%%EOF\n" + b"0" * 512
PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
)
JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00" + b"\x00" * 64
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@contextmanager
def temporary_media_root():
    """Redirects the default storage into a throw-away directory."""

    with tempfile.TemporaryDirectory(prefix="telportal-tests-") as root:
        with override_settings(MEDIA_ROOT=root, STORAGES=STORAGES):
            yield root


def upload(name, content, content_type):
    return SimpleUploadedFile(name, content, content_type=content_type)


class UploadValidationTests(ServiceTestCase):
    """``validate_upload`` is the single gate every upload passes through."""

    def test_a_disallowed_extension_is_rejected(self):
        cases = {
            "payload.exe": "application/octet-stream",
            "script.sh": "application/x-sh",
            "page.html": "text/html",
            "vector.svg": "image/svg+xml",
            "macro.bat": "application/x-msdownload",
        }
        for name, content_type in cases.items():
            with self.subTest(name=name):
                with self.assertRaises(ValidationError) as caught:
                    validate_upload(upload(name, b"harmless bytes", content_type))
                self.assertIn("are not accepted.", str(caught.exception))
                self.assertIn(name.rsplit(".", 1)[1], str(caught.exception))
                self.assertEqual(UploadRecord.objects.count(), 0)

    def test_a_file_whose_bytes_contradict_its_extension_is_rejected(self):
        cases = {
            "report.pdf": (b"MZ\x90\x00\x03\x00\x00\x00" + b"\x00" * 64, "application/pdf"),
            "notes.pdf": (PNG_BYTES, "application/pdf"),
            "photo.png": (JPEG_BYTES, "image/png"),
            "report.docx": (b"just some text", DOCX_MIME),
        }
        for name, (content, content_type) in cases.items():
            with self.subTest(name=name):
                with self.assertRaises(ValidationError) as caught:
                    validate_upload(upload(name, content, content_type))
                self.assertIn(
                    "The file content does not match its file type.",
                    str(caught.exception),
                )

    def test_a_declared_mime_type_that_contradicts_the_extension_is_rejected(self):
        with self.assertRaises(ValidationError) as caught:
            validate_upload(upload("report.pdf", PDF_BYTES, "image/png"))

        self.assertIn("The file content does not match its file type.", str(caught.exception))

    def test_a_file_over_the_size_cap_is_rejected(self):
        oversized = PDF_BYTES + b"0" * (3 * 1024 * 1024)

        with override_settings(MAX_UPLOAD_BYTES=2 * 1024 * 1024):
            with self.assertRaises(ValidationError) as caught:
                validate_upload(upload("big.pdf", oversized, "application/pdf"))

        self.assertIn("Files must be 2.0 MB or smaller.", str(caught.exception))
        self.assertGreater(len(oversized), 2 * 1024 * 1024)

    def test_an_upload_exactly_on_the_size_cap_is_accepted(self):
        exact = PDF_BYTES + b"0" * (2 * 1024 * 1024 - len(PDF_BYTES))

        with override_settings(MAX_UPLOAD_BYTES=2 * 1024 * 1024):
            with temporary_media_root():
                validated = validate_upload(
                    upload("exact.pdf", exact, "application/pdf")
                )

        self.assertEqual(validated.size, 2 * 1024 * 1024)

    def test_an_empty_upload_is_rejected(self):
        with self.assertRaises(ValidationError) as caught:
            validate_upload(upload("empty.pdf", b"", "application/pdf"))

        self.assertIn("The uploaded file is empty.", str(caught.exception))

    def test_a_file_with_no_extension_is_rejected(self):
        with self.assertRaises(ValidationError) as caught:
            validate_upload(upload("noextension", PDF_BYTES, "application/octet-stream"))

        self.assertIn("A file extension is required.", str(caught.exception))

    def test_valid_uploads_of_every_allowed_type_pass(self):
        cases = {
            "handout.pdf": (PDF_BYTES, "application/pdf"),
            "diagram.png": (PNG_BYTES, "image/png"),
            "photo.jpg": (JPEG_BYTES, "image/jpeg"),
        }
        for name, (content, content_type) in cases.items():
            with self.subTest(name=name):
                with temporary_media_root():
                    validated = validate_upload(upload(name, content, content_type))
                self.assertEqual(validated.original_name, name)
                self.assertEqual(validated.content_type, content_type)
                self.assertEqual(validated.size, len(content))
                self.assertEqual(validated.checksum, hashlib.sha256(content).hexdigest())


class UploadStorageTests(ServiceTestCase):
    def test_an_accepted_upload_is_stored_under_a_non_guessable_key(self):
        with temporary_media_root():
            validated = validate_upload(
                upload("uploads/2026/annual report.pdf", PDF_BYTES, "application/pdf")
            )

        key = validated.storage_name
        parts = PurePosixPath(key).parts

        # Exactly two segments: a random directory plus a sanitised file name.
        self.assertEqual(len(parts), 2)
        directory, filename = parts
        self.assertRegex(directory, r"^[0-9a-f]{32}$", f"{directory!r} is not a uuid4 hex token")
        self.assertTrue(filename.endswith(".pdf"))
        self.assertFalse(key.startswith("/"))
        self.assertNotIn("/", filename)
        self.assertNotIn("..", parts)
        self.assertNotIn(".", parts)

        # The client's directory never becomes part of the key, and only the bare
        # file name is kept on the record.
        self.assertEqual(validated.original_name, "annual report.pdf")
        self.assertNotIn("uploads/2026", key)

    def test_two_uploads_of_the_same_file_name_get_different_keys(self):
        with temporary_media_root():
            first = validate_upload(
                upload("annual report.pdf", PDF_BYTES, "application/pdf")
            )
            second = validate_upload(
                upload("annual report.pdf", PDF_BYTES, "application/pdf")
            )

        self.assertNotEqual(first.storage_name, second.storage_name)
        self.assertNotEqual(
            PurePosixPath(first.storage_name).parts[0],
            PurePosixPath(second.storage_name).parts[0],
        )
        self.assertEqual(first.checksum, second.checksum)

    def test_a_traversal_attempt_cannot_escape_the_media_root(self):
        with temporary_media_root() as root:
            validated = validate_upload(
                upload("../../secrets/telport.conf.pdf", PDF_BYTES, "application/pdf")
            )
            from django.core.files.storage import default_storage

            key = validated.storage_name
            self.assertTrue(default_storage.exists(key))
            parts = PurePosixPath(key).parts
            self.assertEqual(len(parts), 2)
            self.assertNotIn("..", parts)
            self.assertNotIn(".", parts)
            written = os.path.realpath(os.path.join(root, *parts))
            self.assertTrue(written.startswith(os.path.realpath(root) + os.sep))

        self.assertEqual(validated.original_name, "telport.conf.pdf")
        self.assertFalse(os.path.exists(os.path.join(root, "..", "secrets")))

    def test_the_recorded_checksum_matches_the_bytes_on_disk(self):
        with temporary_media_root():
            validated = validate_upload(upload("report.pdf", PDF_BYTES, "application/pdf"))
            from django.core.files.storage import default_storage

            with default_storage.open(validated.storage_name, "rb") as handle:
                stored = handle.read()

        self.assertEqual(validated.checksum, hashlib.sha256(PDF_BYTES).hexdigest())
        self.assertEqual(stored, PDF_BYTES)
        self.assertEqual(validated.size, len(PDF_BYTES))


class FileAccessApiTests(ApiTestCase):
    def setUp(self):
        self.graph = build_class()
        self.owner = make_student(self.graph, index=1)
        self.classmate = make_student(self.graph, index=2)
        self.teacher = make_teacher(campus=self.graph.campus)
        # The media root must outlive the request, because the file is streamed
        # from storage rather than from memory.
        context = temporary_media_root()
        context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)

    def _assignment(self, title="Numerical problem set"):
        from django.utils import timezone

        from engagement.models import Assignment

        return Assignment.objects.create(
            title=title,
            subject=self.graph.subject("CS-101"),
            class_room=self.graph.class_room,
            section=self.graph.section,
            teacher=self.teacher,
            description="Show all working.",
            due_on=timezone.localdate(),
            max_marks=20,
            is_published=True,
        )

    def _submit_with_file(self):
        assignment = self._assignment()
        response = self.as_user(self.owner.user).post(
            f"/api/assignments/{assignment.pk}/submissions/",
            {
                "file": upload("solution.pdf", PDF_BYTES, "application/pdf"),
                "notes": "Submitted through the portal.",
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 201, msg=response.content)
        return assignment, UploadRecord.objects.get()

    def test_an_uploaded_file_is_recorded_under_a_random_key(self):
        assignment, record = self._submit_with_file()

        self.assertEqual(record.original_name, "solution.pdf")
        self.assertEqual(record.content_type, "application/pdf")
        self.assertEqual(record.size, len(PDF_BYTES))
        self.assertEqual(record.uploader, self.owner.user)
        self.assertEqual(record.purpose, "SUBMISSION")
        self.assertEqual(record.visibility, "STAFF")
        self.assertEqual(list(record.allowed_user_ids), [self.owner.user.pk])
        self.assertEqual(record.class_room, self.graph.class_room)
        self.assertEqual(assignment.submissions.get().file, record.storage_path)

        parts = PurePosixPath(record.storage_path).parts
        self.assertEqual(len(parts), 2)
        self.assertRegex(parts[0], r"^[0-9a-f]{32}$")
        self.assertEqual(parts[1], "solution.pdf")
        self.assertEqual(record.checksum, hashlib.sha256(PDF_BYTES).hexdigest())

    def test_only_the_owner_and_staff_may_read_the_file(self):
        _, record = self._submit_with_file()
        url = f"/api/files/{record.pk}/"

        for user, allowed in (
            (self.owner.user, True),
            (self.teacher, True),
            (self.classmate.user, False),
        ):
            with self.subTest(user=user.email, allowed=allowed):
                self.as_user(user)
                response = self.client.get(url)
                self.addCleanup(response.close)
                if allowed:
                    self.assertEqual(response.status_code, 200, msg=response.status_code)
                    self.assertEqual(b"".join(response.streaming_content), PDF_BYTES)
                    self.assertEqual(
                        response["Content-Disposition"], 'inline; filename="solution.pdf"'
                    )
                    self.assertEqual(response["X-Content-Type-Options"], "nosniff")
                else:
                    self.assertEqual(response.status_code, 403, msg=response.content)

    def test_an_anonymous_caller_cannot_read_a_file(self):
        _, record = self._submit_with_file()

        response = APIClient().get(f"/api/files/{record.pk}/")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "not_authenticated")

    def test_a_denied_file_access_is_audited(self):
        from core.models import AuditLog

        _, record = self._submit_with_file()

        self.as_user(self.classmate.user)
        response = self.client.get(f"/api/files/{record.pk}/")

        self.assertEqual(response.status_code, 403)
        entry = AuditLog.objects.get(action="file.access_denied")
        self.assertEqual(entry.entity_type, "UploadRecord")
        self.assertEqual(entry.entity_id, str(record.pk))
        self.assertEqual(entry.metadata["purpose"], record.purpose)
        self.assertEqual(entry.actor, self.classmate.user)

    def test_a_rejected_upload_never_creates_a_record_or_a_submission(self):
        assignment = self._assignment("Case study write-up")

        self.as_user(self.owner.user)
        response = self.client.post(
            f"/api/assignments/{assignment.pk}/submissions/",
            {"file": upload("virus.exe", b"MZ\x90\x00binary", "application/octet-stream")},
            format="multipart",
        )

        self.assertEqual(response.status_code, 400, msg=response.content)
        self.assertIn("are not accepted.", str(response.json()["error"]["details"]))
        self.assertEqual(UploadRecord.objects.count(), 0)
        self.assertEqual(assignment.submissions.count(), 0)

    def test_a_signature_mismatch_is_refused_over_the_api(self):
        assignment = self._assignment("Lab report")

        self.as_user(self.owner.user)
        response = self.client.post(
            f"/api/assignments/{assignment.pk}/submissions/",
            {
                "file": upload("report.pdf", b"MZ\x90\x00\x03" + b"\x00" * 32, "application/pdf"),
                "notes": "Looks like a PDF to me.",
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 400, msg=response.content)
        self.assertIn(
            "The file content does not match its file type.",
            str(response.json()["error"]["details"]),
        )
        self.assertEqual(UploadRecord.objects.count(), 0)
        self.assertEqual(assignment.submissions.count(), 0)
