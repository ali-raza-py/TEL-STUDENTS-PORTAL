"""
Development seed data.

    python manage.py seed_demo            # create / refresh demo data
    python manage.py seed_demo --reset    # wipe portal data first
    python manage.py seed_demo --students 24

This is the *only* place demo academic data is written. Nothing in the frontend
or the API carries hardcoded academic values — the portal reads everything from
the database, so seeding is what makes the UI look populated.
"""

from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.timezone import make_aware

from accounts.models import Role, StudentProfile, TeacherProfile, User
from academics.models import (
    AcademicYear,
    Campus,
    ClassRepresentative,
    ClassRoom,
    Program,
    Section,
    Subject,
    SubjectOffering,
    Timetable,
    TimetableEntry,
    TimetableStatus,
    TimetableSubmission,
    Weekday,
)
from assessment.models import (
    ExamType,
    Paper,
    PaperQuestion,
    PaperStatus,
    QuestionType,
    Result,
    ResultItem,
    ResultStatus,
)
from core.models import Notification
from engagement.models import (
    AudienceType,
    AcademicEvent,
    AcademicEventType,
    Announcement,
    Announcement,
    Assignment,
    AssignmentSubmission,
    AssignmentStatus,
    AttendanceRecord,
    AttendanceStatus,
    Feedback,
    RequestStatus,
    RequestType,
    Resource,
    ResourceCategory,
    StudentRequest,
)

DEMO_PASSWORD = "TelPortal@2026"
SEED = 20260927

FIRST_NAMES_M = [
    "Ahmed", "Bilal", "Hamza", "Usman", "Zain", "Faisal", "Omar", "Ali",
    "Yusuf", "Ibrahim", "Kashif", "Danish",
]
FIRST_NAMES_F = [
    "Aisha", "Fatima", "Hira", "Maryam", "Zainab", "Sana", "Iqra", "Noor",
    "Amna", "Rabia", "Mahnoor", "Sadia",
]
LAST_NAMES = [
    "Khan", "Ahmed", "Malik", "Hussain", "Raza", "Sheikh", "Butt", "Chaudhry",
    "Qureshi", "Aslam", "Farooq", "Nawaz",
]

TIMETABLE_GRID = [
    (0, "08:00", "08:45"), (0, "08:45", "09:30"), (0, "09:45", "10:30"),
    (1, "08:00", "08:45"), (1, "09:45", "10:30"), (1, "11:00", "11:45"),
    (2, "08:00", "08:45"), (2, "08:45", "09:30"), (2, "11:00", "11:45"),
    (3, "08:00", "08:45"), (3, "09:45", "10:30"), (3, "11:00", "11:45"),
    (4, "08:00", "08:45"), (4, "08:45", "09:30"), (4, "09:45", "10:30"),
]


def day_offset_safe(exam_date: date) -> int:
    """Days between an exam date and today, never negative."""

    return max(1, (timezone.localdate() - exam_date).days)


class Command(BaseCommand):
    help = "Create realistic development data for the TEL student portal."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete portal data first.")
        parser.add_argument("--students", type=int, default=18, help="Students per class section.")
        parser.add_argument("--quiet", action="store_true", help="Reduce output.")

    @transaction.atomic
    def handle(self, *args, **options):
        random.seed(SEED)
        quiet = options["quiet"]

        def say(message: str) -> None:
            if not quiet:
                self.stdout.write(message)

        if options["reset"]:
            self._reset()
            say("Cleared existing portal data.")

        today = timezone.localdate()
        year = self._academic_year(today)
        campuses = self._campuses()
        programs = self._programs()
        subjects = self._subjects(programs)
        classes, sections = self._classes(campuses, programs, year)
        teachers = self._teachers()
        offerings = self._offerings(classes, sections, subjects, teachers, year)
        students = self._students(options["students"], classes, sections, year)
        self._admin_users()

        timetable = self._timetable(classes, sections, offerings, year)
        self._timetable_submission(classes, sections, students, year)
        papers = self._papers(classes, sections, offerings, subjects, year, teachers)
        self._results(students, offerings, subjects, papers, today)
        self._attendance(students, offerings, today)
        self._assignments(classes, sections, offerings, subjects, teachers, today, students)
        self._resources(subjects, offerings, year, teachers)
        self._announcements(campuses, programs, classes, sections, year, teachers)
        self._events(classes, offerings, today)
        self._requests(students, today)
        self._feedback(students)
        self._notifications(students, timetable, papers, today)

        say("")
        say("Demo data ready. Sign in with any of:")
        say(f"  student  : {students[0].user.email:<38} {DEMO_PASSWORD}")
        say(f"  rep      : {students[1].user.email:<38} {DEMO_PASSWORD}")
        say(f"  teacher  : {'teacher@tel.edu.pk':<38} {DEMO_PASSWORD}")
        say(f"  admin    : {'admin@tel.edu.pk':<38} {DEMO_PASSWORD}")

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def _reset(self) -> None:
        from assessment.models import PracticeAnswer, PracticeAttempt
        from core.models import AuditLog, UploadRecord

        # Delete in dependency order: children before the PROTECTed parents.
        for model in (
            PracticeAnswer, PracticeAttempt, ResultItem, Result,
            PaperQuestion, Paper, AttendanceRecord, AssignmentSubmission, Assignment,
            Resource, Announcement, AcademicEvent, StudentRequest, Feedback,
            Notification, UploadRecord, AuditLog, TimetableSubmission, TimetableEntry,
            Timetable, ClassRepresentative, SubjectOffering, StudentProfile,
            TeacherProfile, Section, ClassRoom, Subject, AcademicYear, Program, Campus,
        ):
            model.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()
        User.objects.filter(is_superuser=True).update(email="admin@tel.edu.pk")

    # ------------------------------------------------------------------
    # Reference data
    # ------------------------------------------------------------------

    def _academic_year(self, today: date) -> AcademicYear:
        start = date(today.year, 8, 1)
        if today.month < 8:
            start = date(today.year - 1, 8, 1)
        end = date(start.year + 1, 7, 31)
        year, _ = AcademicYear.objects.get_or_create(
            code=f"{start.year}-{end.year}",
            defaults={
                "label": f"Academic Year {start.year}–{end.year}",
                "start_date": start,
                "end_date": end,
                "is_current": True,
            },
        )
        return year

    def _campuses(self) -> dict:
        data = [
            ("JIN", "Jinnah Campus", "Main campus, Jinnah Avenue", "+92 21 3455 0100"),
            ("IQB", "Iqbal Campus", "Iqbal Road campus", "+92 21 3455 0200"),
            ("DLK", "D-Link / Doctor Link", "D-Link medical wing", "+92 21 3455 0300"),
        ]
        out = {}
        for code, name, address, phone in data:
            obj, _ = Campus.objects.get_or_create(
                code=code, defaults={"name": name, "address": address, "phone": phone}
            )
            out[code] = obj
        return out

    def _programs(self) -> dict:
        data = [
            ("CS", "Computer Science", Program.Level.XI, "Computer Science Department"),
            ("ENG", "Engineering", Program.Level.XI, "Engineering Department"),
            ("BIO", "Biology / Medical", Program.Level.XI, "Biological Sciences Department"),
        ]
        out = {}
        for code, name, level, department in data:
            obj, _ = Program.objects.get_or_create(
                code=code, defaults={"name": name, "level": level, "department": department}
            )
            out[code] = obj
        return out

    def _subjects(self, programs: dict) -> dict[str, list[Subject]]:
        catalogue = {
            "CS": [
                ("CS-101", "Computer Science", Subject.Kind.BOTH),
                ("CS-102", "Mathematics", Subject.Kind.THEORY),
                ("CS-103", "Physics", Subject.Kind.THEORY),
                ("CS-104", "English", Subject.Kind.THEORY),
                ("CS-105", "Computer Studies", Subject.Kind.PRACTICAL),
            ],
            "ENG": [
                ("EN-101", "Engineering Mathematics", Subject.Kind.THEORY),
                ("EN-102", "Applied Physics", Subject.Kind.THEORY),
                ("EN-103", "Engineering Drawing", Subject.Kind.PRACTICAL),
                ("EN-104", "Technical English", Subject.Kind.THEORY),
            ],
            "BIO": [
                ("BI-101", "Biology", Subject.Kind.THEORY),
                ("BI-102", "Chemistry", Subject.Kind.THEORY),
                ("BI-103", "Physics", Subject.Kind.THEORY),
                ("BI-104", "Medical Terminology", Subject.Kind.THEORY),
            ],
        }
        out: dict[str, list[Subject]] = {}
        for program_code, rows in catalogue.items():
            created = []
            for code, name, kind in rows:
                subject, _ = Subject.objects.get_or_create(
                    code=code,
                    defaults={"name": name, "program": programs[program_code], "kind": kind},
                )
                created.append(subject)
            out[program_code] = created
        return out

    def _classes(self, campuses, programs, year) -> tuple[list, dict]:
        definitions = [
            ("CS", "XI-A", "XI", "JIN", "A"),
            ("CS", "XI-B", "XI", "IQB", "A"),
            ("ENG", "XI-A", "XI", "JIN", "A"),
            ("BIO", "XI-A", "XI", "DLK", "A"),
        ]
        classes: list[ClassRoom] = []
        sections: dict[str, list[Section]] = {}
        for program_code, class_name, level, campus_code, section_name in definitions:
            code = f"{program_code}-{class_name}-{campus_code}"
            class_room, _ = ClassRoom.objects.get_or_create(
                code=code,
                defaults={
                    "name": f"{level} {programs[program_code].name}",
                    "program": programs[program_code],
                    "campus": campuses[campus_code],
                    "academic_year": year,
                },
            )
            section, _ = Section.objects.get_or_create(
                class_room=class_room, name=section_name, defaults={"room": f"Room {101 + len(classes)}"}
            )
            classes.append(class_room)
            sections[code] = [section]
        return classes, sections

    def _teachers(self) -> list[User]:
        from accounts.models import TeacherProfile

        roster = [
            ("teacher@tel.edu.pk", "Rabia Siddiqui", "T-001", "Senior Lecturer"),
            ("t.ali@tel.edu.pk", "Ali Raza", "T-002", "Lecturer"),
            ("t.komal@tel.edu.pk", "Komal Tanveer", "T-003", "Lecturer"),
            ("t.bilal@tel.edu.pk", "Bilal Anwar", "T-004", "Lab Engineer"),
            ("t.sadia@tel.edu.pk", "Sadia Iqbal", "T-005", "Lecturer"),
        ]
        users = []
        for index, (email, name, code, designation) in enumerate(roster):
            user, created = User.objects.get_or_create(
                email=email,
                defaults={"full_name": name, "role": Role.TEACHER, "is_staff": True},
            )
            if email == "teacher@tel.edu.pk":
                user.set_password(DEMO_PASSWORD)
                user.full_name = name
                user.role = Role.TEACHER
                user.is_staff = True
                user.save(update_fields=["password", "full_name", "role", "is_staff"])
            TeacherProfile.objects.get_or_create(
                user=user, defaults={"employee_code": code, "designation": designation}
            )
            user.teacher_profile.subjects.set(Subject.objects.all()[:3])
            users.append(user)
        return users

    def _offerings(self, classes, sections, subjects, teachers, year) -> dict[str, list[SubjectOffering]]:
        out: dict[str, list[SubjectOffering]] = {}
        for index, class_room in enumerate(classes):
            program_code = class_room.program.code
            offered = []
            for position, subject in enumerate(subjects[program_code]):
                offering, _ = SubjectOffering.objects.get_or_create(
                    class_room=class_room,
                    section=sections[class_room.code][0],
                    subject=subject,
                    academic_year=year,
                    defaults={"teacher": teachers[(index + position) % len(teachers)]},
                )
                offered.append(offering)
            out[class_room.code] = offered
        return out

    # ------------------------------------------------------------------
    # People
    # ------------------------------------------------------------------

    def _students(self, per_section: int, classes, sections, year) -> list[StudentProfile]:
        profiles: list[StudentProfile] = []
        counter = 1
        # Keep the first two accounts stable so the documented demo
        # credentials work after every fresh seed.
        demo_accounts = {
            1: ("student01@tel.edu.pk", "Student One"),
            2: ("student02@tel.edu.pk", "Student Two"),
        }
        for class_room in classes:
            section = sections[class_room.code][0]
            for index in range(per_section):
                female = index % 3 == 0
                first = random.choice(FIRST_NAMES_F if female else FIRST_NAMES_M)
                last = random.choice(LAST_NAMES)
                full_name = f"{first} {last}"
                slug = f"{first}.{last}{index}".lower().replace("'", "")
                email = f"{slug}.{class_room.code.lower()[:2]}@student.tel.edu.pk"
                if counter in demo_accounts:
                    email, full_name = demo_accounts[counter]
                student_number = counter
                code = f"TEL-{class_room.program.code}-{student_number:04d}"
                counter += 1

                # Reuse existing profiles on a non-destructive re-seed. This
                # also upgrades older generated datasets to the documented
                # student01/student02 account names without losing their work.
                profile = StudentProfile.objects.select_related("user").filter(student_code=code).first()
                if profile is None:
                    user, created = User.objects.get_or_create(
                        email=email,
                        defaults={"full_name": full_name, "role": Role.STUDENT},
                    )
                    if created or student_number in demo_accounts:
                        user.set_password(DEMO_PASSWORD)
                        user.save(update_fields=["password"])
                    profile = StudentProfile.objects.create(
                        student_code=code,
                        user=user,
                        roll_number=str(index + 1),
                        campus=class_room.campus,
                        program=class_room.program,
                        class_room=class_room,
                        section=section,
                        academic_year=year,
                        admission_date=date(year.start_date.year, 8, 15),
                        guardian_name=f"{random.choice(LAST_NAMES)} family",
                        guardian_relation=random.choice(["Father", "Mother", "Guardian"]),
                        guardian_phone=f"+92 3{random.randint(10, 49)} {random.randint(1000000, 9999999)}",
                        blood_group=random.choice(["A+", "B+", "O+", "AB+", "O-"]),
                    )
                elif student_number in demo_accounts:
                    user = profile.user
                    user.email = email
                    user.full_name = full_name
                    user.role = Role.STUDENT
                    user.set_password(DEMO_PASSWORD)
                    user.save(update_fields=["email", "full_name", "role", "password"])
                profiles.append(profile)
        return profiles

    def _admin_users(self) -> None:
        for email, name, role, staff in (
            ("admin@tel.edu.pk", "TEL Administrator", Role.ADMIN, True),
            ("registrar@tel.edu.pk", "Registrar Office", Role.ADMIN, True),
        ):
            user, created = User.objects.get_or_create(
                email=email, defaults={"full_name": name, "role": role, "is_staff": staff}
            )
            if email == "admin@tel.edu.pk":
                user.set_password(DEMO_PASSWORD)
                user.full_name = name
                user.role = role
                user.is_staff = staff
                user.save(update_fields=["password", "full_name", "role", "is_staff"])

    # ------------------------------------------------------------------
    # Timetable
    # ------------------------------------------------------------------

    def _timetable(self, classes, sections, offerings, year) -> dict[str, Timetable]:
        """A published timetable for every class section."""

        published: dict[str, Timetable] = {}
        for class_index, class_room in enumerate(classes):
            section = sections[class_room.code][0]
            subject_list = offerings[class_room.code]

            timetable, created = Timetable.objects.get_or_create(
                class_room=class_room,
                section=section,
                academic_year=year,
                version=1,
                defaults={
                    "status": TimetableStatus.PUBLISHED,
                    "title": f"{class_room.name} — {section.name} weekly timetable",
                    "effective_from": timezone.localdate() - timedelta(days=14),
                    "source": "TEL_CORE",
                    "published_at": timezone.now() - timedelta(days=14),
                },
            )
            if created:
                for position, (day, start, end) in enumerate(TIMETABLE_GRID):
                    offering = subject_list[(position + class_index) % len(subject_list)]
                    TimetableEntry.objects.create(
                        timetable=timetable,
                        day_of_week=day,
                        start_time=time(*map(int, start.split(":"))),
                        end_time=time(*map(int, end.split(":"))),
                        subject=offering.subject,
                        teacher=offering.teacher,
                        room=section.room or f"Room {101 + day}",
                        campus=class_room.campus,
                    )
            published[class_room.code] = timetable
        return published

    def _timetable_submission(self, classes, sections, students, year) -> None:
        """A pending representative submission so the review workflow is visible."""

        class_room = classes[0]
        section = sections[class_room.code][0]
        class_students = [
            profile
            for profile in students
            if profile.class_room_id == class_room.pk and profile.section_id == section.pk
        ]
        # student02@tel.edu.pk is the documented class representative.
        rep = class_students[1] if len(class_students) > 1 else None
        if rep is None:
            return
        active_rep = ClassRepresentative.objects.filter(
            class_room=class_room, section=section, is_active=True
        ).first()
        if active_rep is not None:
            if active_rep.user_id != rep.user_id:
                former_rep = active_rep.user
                former_rep.role = Role.STUDENT
                former_rep.save(update_fields=["role"])
                active_rep.user = rep.user
                active_rep.save(update_fields=["user"])
            rep.user.role = Role.CLASS_REPRESENTATIVE
            rep.user.save(update_fields=["role"])
            return
        if TimetableSubmission.objects.filter(class_room=class_room, section=section).exists():
            return
        rep.user.role = Role.CLASS_REPRESENTATIVE
        rep.user.save(update_fields=["role"])
        ClassRepresentative.objects.get_or_create(
            class_room=class_room,
            section=section,
            user=rep.user,
            defaults={"assigned_by": User.objects.filter(role=Role.ADMIN).first(), "is_active": True},
        )
        TimetableSubmission.objects.create(
            class_room=class_room,
            section=section,
            academic_year=year,
            submitted_by=rep.user,
            status=TimetableStatus.SUBMITTED,
            summary="Room 204 is under renovation — Thursday practical moved to Lab B.",
            change_note=(
                "Engineering drawing practical on Thursday 09:45 moves to Lab B until repairs finish."
            ),
            entries_payload=[],
        )

    # ------------------------------------------------------------------
    # Papers
    # ------------------------------------------------------------------

    #: (exam type, lifecycle state, day offset, total marks, minutes, questions, topic metadata)
    PAPER_PLAN = (
        (ExamType.MONTHLY_TEST, PaperStatus.PRACTICE_AVAILABLE, -21, 50, 30, 8, "topic"),
        (ExamType.WEEKLY_TEST, PaperStatus.PRACTICE_AVAILABLE, -12, 25, 20, 5, "topic"),
        (ExamType.MIDTERM, PaperStatus.PUBLISHED, -30, 50, 45, 8, "topic"),
        (ExamType.MONTHLY_TEST, PaperStatus.PRACTICE_AVAILABLE, -5, 40, 30, 6, ""),
        (ExamType.MOCK, PaperStatus.PUBLISHED, 6, 50, 60, 10, "topic"),
    )

    def _papers(self, classes, sections, offerings, subjects, year, teachers) -> list[Paper]:
        """Every class gets its own paper archive, in the same TEL lifecycle states."""

        papers: list[Paper] = []
        today = timezone.localdate()

        for class_index, class_room in enumerate(classes):
            section = sections[class_room.code][0]
            subject_list = offerings[class_room.code]
            for subject_index, offering in enumerate(subject_list):
                exam_type, status, day_offset, total, duration, count, metadata = self.PAPER_PLAN[
                    subject_index % len(self.PAPER_PLAN)
                ]
                exam_date = today + timedelta(days=day_offset + class_index)
                paper, created = Paper.objects.get_or_create(
                    external_ref=f"DEMO-P{class_room.code}-{subject_index + 1}",
                    defaults=self._paper_defaults(
                        class_room=class_room,
                        section=section,
                        offering=offering,
                        exam_type=exam_type,
                        status=status,
                        exam_date=exam_date,
                        total=total,
                        duration=duration,
                        teacher=teachers[(class_index + subject_index) % len(teachers)],
                    ),
                )
                if created:
                    self._questions(paper, offering.subject, count, metadata)
                papers.append(paper)

            # A deep past-paper archive entry and a draft awaiting verification.
            past_date = today - timedelta(days=75)
            past, created = Paper.objects.get_or_create(
                external_ref=f"DEMO-PAST-{class_room.code}",
                defaults=self._paper_defaults(
                    class_room=class_room,
                    section=section,
                    offering=subject_list[0],
                    exam_type=ExamType.PAST,
                    status=PaperStatus.PRACTICE_AVAILABLE,
                    exam_date=past_date,
                    total=50,
                    duration=45,
                    teacher=teachers[class_index % len(teachers)],
                ),
            )
            if created:
                self._questions(past, subject_list[0].subject, 8, "")
            papers.append(past)

            draft, created = Paper.objects.get_or_create(
                external_ref=f"DEMO-DRAFT-{class_room.code}",
                defaults=self._paper_defaults(
                    class_room=class_room,
                    section=section,
                    offering=subject_list[min(1, len(subject_list) - 1)],
                    exam_type=ExamType.MIDTERM,
                    status=PaperStatus.DRAFT,
                    exam_date=today + timedelta(days=12),
                    total=50,
                    duration=45,
                    teacher=teachers[class_index % len(teachers)],
                    verified=False,
                ),
            )
            if created:
                self._questions(draft, subject_list[min(1, len(subject_list) - 1)].subject, 8, "")
            papers.append(draft)
        return papers

    def _paper_defaults(self, *, class_room, section, offering, exam_type, status, exam_date,
                        total, duration, teacher, verified=True) -> dict:
        released = status in {PaperStatus.PUBLISHED, PaperStatus.PRACTICE_AVAILABLE}
        return {
            "title": (
                f"{offering.subject.name} {exam_type.replace('_', ' ').title()} "
                f"{exam_date.strftime('%b %Y')}"
            ),
            "subject": offering.subject,
            "class_room": class_room,
            "section": section,
            "campus": class_room.campus,
            "academic_year": class_room.academic_year,
            "teacher": teacher,
            "exam_type": exam_type,
            "total_marks": total,
            "duration_minutes": duration,
            "exam_date": exam_date,
            "status": status,
            "source": Paper.Source.TEL_CORE,
            "instructions": (
                "Answer every question. Write your working clearly for the questions that "
                "carry more than one mark. Calculators are not permitted."
            ),
            "published_at": timezone.now() - timedelta(days=max(1, -day_offset_safe(exam_date))) if released else None,
            "verified_by": teacher if verified else None,
            "verified_at": timezone.now() if verified else None,
        }

    QUESTION_STEMS = (
        "Which of the following best describes the principle being applied here?",
        "State the correct relationship and justify your answer in one line.",
        "A student repeats the experiment with one variable changed. What would you expect?",
        "The diagram below is not to scale. Identify the correct conclusion.",
        "Choose the option that correctly completes the definition.",
    )

    def _questions(self, paper: Paper, subject: Subject, count: int, metadata: str) -> None:
        chapters = ["Introduction", "Core concepts", "Applications"]
        topics = ["Fundamentals", "Measurement", "Application", "Analysis", "Review"]
        for order in range(1, count + 1):
            if order % 5 == 0:
                qtype = QuestionType.SUBJECTIVE
            elif order % 4 == 0:
                qtype = QuestionType.TRUE_FALSE
            else:
                qtype = QuestionType.MCQ
            options = (
                [f"Statement {chr(65 + i)}" for i in range(4)]
                if qtype == QuestionType.MCQ
                else ["True", "False"]
                if qtype == QuestionType.TRUE_FALSE
                else []
            )
            correct = random.randint(0, len(options) - 1) if options else None
            chapter = chapters[(order - 1) % len(chapters)]
            PaperQuestion.objects.create(
                paper=paper,
                order=order,
                question_type=qtype,
                text=(
                    f"{subject.name} — {chapter} ({order}). "
                    f"{self.QUESTION_STEMS[(order - 1) % len(self.QUESTION_STEMS)]}"
                ),
                options=options,
                marks=round(paper.total_marks / count, 2),
                chapter=chapter if metadata else "",
                topic=topics[(order - 1) % len(topics)] if metadata == "topic" else "",
                correct_option=correct,
                answer_key_text=(
                    "Written answer — marked by your subject teacher."
                    if qtype == QuestionType.SUBJECTIVE
                    else ""
                ),
                explanation=(
                    f"See the {subject.name} notes, chapter '{chapter}'."
                    if correct is not None
                    else ""
                ),
            )

    # ------------------------------------------------------------------
    # Results
    # ------------------------------------------------------------------

    def _results(self, students, offerings, subjects, papers, today) -> None:
        """Published results only — students must never see a draft."""

        for class_code, subject_offerings in offerings.items():
            roster = [p for p in students if p.class_room.code == class_code]
            if not roster:
                continue
            for subject_index, offering in enumerate(subject_offerings):
                for round_index, days_ago in enumerate((45, 30, 16, 4)):
                    exam_date = today - timedelta(days=days_ago)
                    exam_type = (
                        ExamType.MONTHLY_TEST if round_index % 2 == 0 else ExamType.WEEKLY_TEST
                    )
                    total = 50
                    for student_index, profile in enumerate(roster):
                        # Deterministic spread so the class has a real bell curve.
                        base = 52 + ((student_index * 7 + subject_index * 5 + round_index * 3) % 44)
                        obtained = round(total * min(0.98, base / 100), 1)
                        percentage = round(obtained / total * 100, 2)
                        from assessment.services import grade_for

                        name, created = Result.objects.get_or_create(
                            student=profile,
                            assessment_name=f"{offering.subject.name} "
                            f"{exam_type.replace('_', ' ').title()} {exam_date.strftime('%b %Y')}",
                            assessment_type=exam_type,
                            defaults={
                                "subject": offering.subject,
                                "assessment_date": exam_date,
                                "total_marks": total,
                                "obtained_marks": obtained,
                                "percentage": percentage,
                                "grade": grade_for(percentage),
                                "status": ResultStatus.PUBLISHED,
                                "published_at": make_aware(
                                    datetime.combine(exam_date + timedelta(days=3), time(17, 0))
                                ),
                                "position_in_class": (student_index % 24) + 1,
                            },
                        )
                        if created and round_index in (1, 3):
                            self._result_items(name, offering.subject, round_index)

    def _result_items(self, result: Result, subject: Subject, round_index: int) -> None:
        topics = ["Fundamentals", "Measurement", "Application", "Analysis"]
        for position, topic in enumerate(topics):
            total = 12
            ratio = 0.45 + ((position * 0.12 + round_index * 0.05) % 0.5)
            ResultItem.objects.create(
                result=result,
                question_label=f"Q{position + 1}",
                chapter=["Introduction", "Core concepts", "Applications", "Review"][position % 4],
                topic=topic,
                marks_awarded=round(total * ratio, 1),
                marks_total=total,
            )

    # ------------------------------------------------------------------
    # Attendance
    # ------------------------------------------------------------------

    def _attendance(self, students, offerings, today) -> None:
        weekdays = [0, 1, 2, 3, 4]
        for student in students:
            offerings_for_class = offerings.get(student.class_room.code, [])
            for offset in range(0, 90, 1):
                day = today - timedelta(days=offset)
                if day.weekday() not in weekdays or day.weekday() > 4:
                    continue
                for position, offering in enumerate(offerings_for_class):
                    if (offset + position) % 3 == 0:
                        continue  # subject not scheduled that day
                    roll = random.random()
                    if roll < 0.86:
                        status_value = AttendanceStatus.PRESENT
                    elif roll < 0.93:
                        status_value = AttendanceStatus.LATE
                    elif roll < 0.985:
                        status_value = AttendanceStatus.ABSENT
                    else:
                        status_value = AttendanceStatus.EXCUSED
                    AttendanceRecord.objects.get_or_create(
                        student=student,
                        subject=offering.subject,
                        date=day,
                        defaults={
                            "class_room": student.class_room,
                            "status": status_value,
                            "period_label": f"P{position + 1}",
                        },
                    )

    # ------------------------------------------------------------------
    # Engagement content
    # ------------------------------------------------------------------

    ASSIGNMENT_PLAN = (
        (-3, "Question sheet 4"),
        (4, "Numerical problem set"),
        (12, "Case study write-up"),
    )

    def _assignments(self, classes, sections, offerings, subjects, teachers, today, students) -> None:
        for class_room in classes:
            section = sections[class_room.code][0]
            roster = [
                p
                for p in students
                if p.class_room_id == class_room.pk and p.section_id == section.pk
            ]
            for index, offering in enumerate(offerings[class_room.code]):
                for offset, title in self.ASSIGNMENT_PLAN:
                    assignment, created = Assignment.objects.get_or_create(
                        title=f"{offering.subject.name} — {title}",
                        class_room=class_room,
                        section=section,
                        defaults={
                            "subject": offering.subject,
                            "teacher": offering.teacher,
                            "description": (
                                f"Complete the {title.lower()} for {offering.subject.name}. "
                                "Show all working; marks are awarded for method."
                            ),
                            "assigned_on": today + timedelta(days=offset - 5),
                            "due_on": today + timedelta(days=offset),
                            "max_marks": 20,
                            "is_published": True,
                            "published_at": timezone.now() - timedelta(days=5),
                        },
                    )
                    if created and offset == 4 and roster:
                        for position, profile in enumerate(roster[:4]):
                            AssignmentSubmission.objects.create(
                                assignment=assignment,
                                student=profile,
                                status=(
                                    AssignmentStatus.REVIEWED
                                    if position < 2
                                    else AssignmentStatus.SUBMITTED
                                    if position < 3
                                    else AssignmentStatus.LATE
                                ),
                                notes="Submitted through the portal.",
                                marks_awarded=16 + position if position < 2 else None,
                                feedback="Good method, watch unit consistency." if position < 2 else "",
                                reviewed_by=teachers[0] if position < 2 else None,
                            )

    def _resources(self, subjects, offerings, year, teachers) -> None:
        catalogue = [
            (ResourceCategory.NOTES, "Chapter notes — fundamentals", "Notes"),
            (ResourceCategory.NOTES, "Worked example booklet", "Notes"),
            (ResourceCategory.SYLLABUS, "Course syllabus and scheme of study", "Syllabus"),
            (ResourceCategory.STUDY_MATERIAL, "Revision quick sheet", "Study material"),
            (ResourceCategory.PREVIOUS_PAPERS, "Previous paper with answer key", "Previous papers"),
            (ResourceCategory.ANSWER_KEYS, "Midterm answer key", "Answer keys"),
            (ResourceCategory.FORMS, "Practical record book template", "Forms"),
            (ResourceCategory.NOTICES, "Lab safety notice", "Notices"),
        ]
        for program_code, subject_list in subjects.items():
            for subject in subject_list:
                for category, title, description in catalogue[: 2 + (len(subject.code) % 4)]:
                    Resource.objects.get_or_create(
                        title=f"{subject.name} — {title}",
                        subject=subject,
                        category=category,
                        defaults={
                            "description": description,
                            "academic_year": year,
                            "uploaded_by": teachers[0],
                            "is_published": True,
                            "published_at": timezone.now() - timedelta(days=random.randint(3, 60)),
                            "chapter": "Introduction" if "Chapter" in title else "",
                        },
                    )

    #: (title, body, audience, campus code, class index or None, pinned)
    ANNOUNCEMENT_PLAN = (
        (
            "Monthly Test 02 results have been published",
            "Results for the second monthly test cycle are now live in the portal. "
            "Check your result and review the answer key from the practice archive.",
            AudienceType.CLASS,
            None,
            0,
            True,
        ),
        (
            "Monthly Test 03 schedule",
            "The next monthly test window opens on the first Monday of next month. "
            "The full timetable is available under Timetable.",
            AudienceType.ALL_STUDENTS,
            None,
            None,
            True,
        ),
        (
            "Iqbal Campus — assembly on Thursday",
            "All Iqbal Campus students assemble in the main courtyard at 08:00 on Thursday.",
            AudienceType.CAMPUS,
            "IQB",
            None,
            False,
        ),
        (
            "Lab safety notice for practical sessions",
            "Closed shoes and a lab coat are mandatory for all practical sessions this term.",
            AudienceType.PROGRAM,
            None,
            None,
            False,
        ),
        (
            "Library week: extended timings",
            "The TEL library will remain open until 18:00 during library week.",
            AudienceType.ACADEMIC_YEAR,
            None,
            None,
            False,
        ),
    )

    def _announcements(self, campuses, programs, classes, sections, year, teachers) -> None:
        for class_index, class_room in enumerate(classes):
            for slot, (title, body, audience, campus_code, target_index, pinned) in enumerate(
                self.ANNOUNCEMENT_PLAN
            ):
                scoped_title = title if target_index is None else f"{title} — {class_room.name}"
                if Announcement.objects.filter(title=scoped_title).exists():
                    continue
                section = sections[class_room.code][0] if target_index is not None else None
                announcement = Announcement.objects.create(
                    title=scoped_title,
                    body=body,
                    audience=audience,
                    campus=campuses[campus_code] if campus_code else None,
                    program=programs[class_room.program.code]
                    if audience == AudienceType.PROGRAM
                    else None,
                    class_room=classes[target_index] if target_index is not None else None,
                    section=section,
                    academic_year=year if audience == AudienceType.ACADEMIC_YEAR else None,
                    is_pinned=pinned and class_index == 0,
                    published_at=timezone.now() - timedelta(days=1 + (class_index * 2 + slot) % 9),
                    created_by=teachers[(class_index + slot) % len(teachers)],
                )
                self._fan_out_announcement(announcement)

    def _fan_out_announcement(self, announcement: Announcement) -> None:
        from core.notifications import notify

        for profile in StudentProfile.objects.select_related("user").all():
            if announcement.targets(profile):
                notify(
                    profile.user,
                    category="ANNOUNCEMENT",
                    title=announcement.title,
                    body=announcement.body[:240],
                    action_url="/announcements",
                    action_label="Read announcement",
                    dedupe_key=f"announcement:{announcement.pk}",
                )

    def _events(self, classes, offerings, today) -> None:
        plan = [
            ("Monthly Test 03", AcademicEventType.TEST, 2, 10, 0, True),
            ("Project submission deadline", AcademicEventType.ASSIGNMENT_DUE, 5, 23, 59, True),
            ("Midterm examination week begins", AcademicEventType.EXAM, 12, 9, 0, True),
            ("Result publication — end of term cycle", AcademicEventType.RESULT_PUBLICATION, 18, 15, 0, False),
            ("Founder's Day holiday", AcademicEventType.HOLIDAY, 24, 0, 0, False),
            ("Career guidance session", AcademicEventType.TEL_EVENT, 31, 11, 0, False),
        ]
        for class_index, class_room in enumerate(classes):
            for index, (title, event_type, offset, hour, minute, class_scoped) in enumerate(plan):
                scoped_title = f"{title} — {class_room.name}" if class_scoped else title
                if AcademicEvent.objects.filter(title=scoped_title).exists():
                    continue
                start = make_aware(
                    datetime.combine(
                        today + timedelta(days=offset), time(hour, minute)
                    )
                )
                AcademicEvent.objects.create(
                    title=scoped_title,
                    event_type=event_type,
                    starts_at=start,
                    ends_at=start + timedelta(hours=2),
                    is_all_day=event_type == AcademicEventType.HOLIDAY,
                    class_room=class_room if class_scoped else None,
                    subject=offerings[class_room.code][0].subject
                    if class_scoped and event_type == AcademicEventType.TEST
                    else None,
                )

    def _requests(self, students, today) -> None:
        sample = [
            (
                RequestType.ATTENDANCE_CORRECTION,
                "Attendance marked absent on a day I attended",
                "I was present in the Physics practical on the 12th but the register shows absent.",
                RequestStatus.RESOLVED,
                "Register corrected — the session was recorded under the wrong period. Thanks for flagging it.",
            ),
            (
                RequestType.TIMETABLE_ISSUE,
                "Thursday practical room changed",
                "The timetable still shows Room 204 for Thursday practical. Has it moved to Lab B?",
                RequestStatus.IN_REVIEW,
                "",
            ),
            (
                RequestType.DOCUMENT,
                "Request for a bonafide certificate",
                "I need a bonafide certificate for a university application due next week.",
                RequestStatus.PENDING,
                "",
            ),
        ]
        for index, (kind, subject_line, description, state, response) in enumerate(sample):
            profile = students[index % len(students)]
            if StudentRequest.objects.filter(subject_line=subject_line).exists():
                continue
            StudentRequest.objects.create(
                student=profile,
                request_type=kind,
                subject_line=subject_line,
                description=description,
                status=state,
                admin_response=response,
                responded_by=User.objects.filter(role=Role.ADMIN).first() if response else None,
                responded_at=timezone.now() if response else None,
            )

    def _feedback(self, students) -> None:
        samples = [
            ("PORTAL", 5, "The timetable view is much easier to read on my phone now."),
            ("RESOURCES", 4, "More past papers with answer keys would help before the midterm."),
            ("TIMETABLE", 3, "The Thursday practical keeps moving. A notification would help."),
            ("COMMUNICATION", 5, "Getting results here instead of waiting for a message is a big help."),
        ]
        for index, (category, rating, message) in enumerate(samples):
            profile = students[index % len(students)]
            if Feedback.objects.filter(student=profile, message=message).exists():
                continue
            Feedback.objects.create(student=profile, category=category, rating=rating, message=message)

    def _notifications(self, students, timetables, papers, today) -> None:
        from core.notifications import notify

        roster = students[:20]
        practice_paper = next(
            (p for p in papers if p.status == PaperStatus.PRACTICE_AVAILABLE), None
        )
        for index, profile in enumerate(roster):
            timetable = timetables.get(profile.class_room.code)
            if timetable is not None:
                notify(
                    profile.user,
                    category="TIMETABLE",
                    title="Your class timetable has been updated.",
                    body=(
                        f"Timetable v{timetable.version} is live for "
                        f"{profile.class_room.name} — {profile.section.name}."
                    ),
                    action_url="/timetable",
                    action_label="View timetable",
                    dedupe_key=f"timetable-published:{timetable.pk}",
                )
            own_practice = next(
                (
                    p
                    for p in papers
                    if p.class_room_id == profile.class_room_id
                    and p.status == PaperStatus.PRACTICE_AVAILABLE
                ),
                practice_paper,
            )
            if own_practice is not None:
                notify(
                    profile.user,
                    category="PAPER",
                    title="A new paper is available in the practice archive",
                    body=f"{own_practice.title} — {own_practice.subject.name}.",
                    action_url=f"/papers/{own_practice.pk}",
                    action_label="Open paper",
                    dedupe_key=f"paper-available:{own_practice.pk}",
                )
            if index % 3 == 0:
                notify(
                    profile.user,
                    category="ASSIGNMENT",
                    title="Assignment due in 4 days",
                    body="A submission deadline is coming up. Open Assignments to review it.",
                    action_url="/assignments",
                    action_label="View assignment",
                    dedupe_key=f"assignment-due:{profile.pk}",
                )
