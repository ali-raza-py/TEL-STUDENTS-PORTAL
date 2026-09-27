"""
Shared object factories for the automated test suite.

Every test module builds its data through these helpers so the whole suite uses
one small, explicit, deterministic graph:

    Campus -> Program -> AcademicYear -> ClassRoom -> Section
          -> Subject -> SubjectOffering
    User  -> StudentProfile

``seed_demo`` is deliberately *not* used from tests: it writes a lot of data and
the tests need exact, hand-picked values (marks, statuses, dates) to assert on.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time, timedelta
from typing import Sequence

from django.utils import timezone

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
from engagement.models import AttendanceRecord, AttendanceStatus

#: One password for every factory-created account, so no test depends on a
#: particular hash or on the ordering of user creation.
DEMO_PASSWORD = "TelPortal@Test2026"

SUBJECT_CATALOGUE: tuple[tuple[str, str], ...] = (
    ("CS-101", "Computer Science"),
    ("CS-102", "Mathematics"),
    ("CS-103", "Physics"),
)


# ---------------------------------------------------------------------------
# Academic graph
# ---------------------------------------------------------------------------


@dataclass
class ClassGraph:
    """A campus / programme / class / section together with its offerings."""

    key: str
    campus: Campus
    program: Program
    academic_year: AcademicYear
    class_room: ClassRoom
    section: Section
    subjects: dict[str, Subject]
    offerings: dict[str, SubjectOffering]

    def subject(self, code: str) -> Subject:
        return self.subjects[code]

    def offering(self, code: str) -> SubjectOffering:
        return self.offerings[code]


def make_campus(*, code: str = "JIN", name: str = "Jinnah Campus") -> Campus:
    campus, _ = Campus.objects.get_or_create(code=code, defaults={"name": name})
    return campus


def make_program(*, code: str = "CS", name: str = "Computer Science") -> Program:
    program, _ = Program.objects.get_or_create(code=code, defaults={"name": name})
    return program


def make_academic_year(*, code: str = "2025-2026") -> AcademicYear:
    year, _ = AcademicYear.objects.get_or_create(
        code=code,
        defaults={
            "label": f"Academic Year {code}",
            "start_date": date(2025, 8, 1),
            "end_date": date(2026, 7, 31),
            "is_current": True,
        },
    )
    return year


def build_class(
    *,
    key: str = "A",
    subjects: Sequence[tuple[str, str]] = SUBJECT_CATALOGUE,
) -> ClassGraph:
    """
    Creates a complete, placeable class.

    ``key`` distinguishes classes inside one test (``build_class(key="A")`` and
    ``build_class(key="B")``). Subjects are shared between classes of the same
    programme — only the offerings are per class, which is what the timetable
    validation actually keys off.
    """

    campus = make_campus()
    program = make_program()
    year = make_academic_year()

    class_room, _ = ClassRoom.objects.get_or_create(
        code=f"CS-XI-{key}",
        defaults={
            "name": f"XI Computer Science {key}",
            "program": program,
            "campus": campus,
            "academic_year": year,
        },
    )
    section, _ = Section.objects.get_or_create(
        class_room=class_room,
        name="A",
        defaults={"room": f"Room {key}", "capacity": 40},
    )

    subject_rows: dict[str, Subject] = {}
    offerings: dict[str, SubjectOffering] = {}
    for code, name in subjects:
        subject, _ = Subject.objects.get_or_create(
            code=code, defaults={"name": name, "program": program}
        )
        offering, _ = SubjectOffering.objects.get_or_create(
            class_room=class_room,
            section=section,
            subject=subject,
            academic_year=year,
        )
        subject_rows[code] = subject
        offerings[code] = offering

    return ClassGraph(
        key=key,
        campus=campus,
        program=program,
        academic_year=year,
        class_room=class_room,
        section=section,
        subjects=subject_rows,
        offerings=offerings,
    )


# ---------------------------------------------------------------------------
# People
# ---------------------------------------------------------------------------


def make_admin(*, email: str = "admin@tel.edu.pk", full_name: str = "TEL Administrator") -> User:
    return User.objects.create_user(
        email=email,
        password=DEMO_PASSWORD,
        full_name=full_name,
        role=Role.ADMIN,
        is_staff=True,
    )


def make_teacher(
    *,
    email: str = "teacher@tel.edu.pk",
    full_name: str = "Rabia Siddiqui",
    campus: Campus | None = None,
    employee_code: str = "T-001",
) -> User:
    user, _ = User.objects.get_or_create(
        email=email, defaults={"full_name": full_name, "role": Role.TEACHER, "is_staff": True}
    )
    user.set_password(DEMO_PASSWORD)
    user.save()
    TeacherProfile.objects.get_or_create(
        user=user, defaults={"employee_code": employee_code, "campus": campus}
    )
    return user


def make_student(
    graph: ClassGraph,
    *,
    index: int = 1,
    role: str = Role.STUDENT,
    full_name: str | None = None,
) -> StudentProfile:
    user = User.objects.create_user(
        email=f"student{index}.{graph.key}@student.tel.edu.pk",
        password=DEMO_PASSWORD,
        full_name=full_name or f"Student {index} of {graph.key}",
        role=role,
    )
    return StudentProfile.objects.create(
        user=user,
        student_code=f"TEL-{graph.key}-{index:03d}",
        roll_number=str(index),
        campus=graph.campus,
        program=graph.program,
        class_room=graph.class_room,
        section=graph.section,
        academic_year=graph.academic_year,
    )


def make_representative(
    graph: ClassGraph,
    *,
    index: int = 1,
    assigned_by: User | None = None,
) -> tuple[User, StudentProfile, ClassRepresentative]:
    """A student promoted to the active class representative of ``graph``."""

    profile = make_student(graph, index=index)
    profile.user.role = Role.CLASS_REPRESENTATIVE
    profile.user.save(update_fields=["role"])
    record = ClassRepresentative.objects.create(
        class_room=graph.class_room,
        section=graph.section,
        user=profile.user,
        assigned_by=assigned_by,
    )
    return profile.user, profile, record


# ---------------------------------------------------------------------------
# Timetable
# ---------------------------------------------------------------------------


def make_entries_payload(*subject_codes: str, day: int = 0, start: str = "08:00") -> list[dict]:
    """A valid, non-overlapping list of timetable periods for a submission."""

    payload: list[dict] = []
    hour, minute = (int(part) for part in start.split(":"))
    for index, code in enumerate(subject_codes):
        begins = hour * 60 + minute + 45 * index
        ends = begins + 40
        payload.append(
            {
                "day": day,
                "start": f"{begins // 60:02d}:{begins % 60:02d}",
                "end": f"{ends // 60:02d}:{ends % 60:02d}",
                "subject_code": code,
                "room": "Room 101",
            }
        )
    return payload


def make_timetable(
    graph: ClassGraph,
    *,
    version: int = 1,
    status: str = TimetableStatus.PUBLISHED,
    subject_codes: Sequence[str] = ("CS-101",),
    published: bool | None = None,
) -> Timetable:
    timetable = Timetable.objects.create(
        class_room=graph.class_room,
        section=graph.section,
        academic_year=graph.academic_year,
        version=version,
        status=status,
        title=f"{graph.class_room.name} — {graph.section.name} weekly timetable",
        source="TEL_CORE",
        published_at=(
            timezone.now() if (published if published is not None else status == TimetableStatus.PUBLISHED) else None
        ),
    )
    for index, code in enumerate(subject_codes):
        TimetableEntry.objects.create(
            timetable=timetable,
            day_of_week=index % 5,
            start_time=time(8, 0),
            end_time=time(8, 45),
            subject=graph.subject(code),
            room=graph.section.room,
            campus=graph.campus,
        )
    return timetable


# ---------------------------------------------------------------------------
# Papers and questions
# ---------------------------------------------------------------------------


def make_paper(
    graph: ClassGraph,
    *,
    subject_code: str = "CS-101",
    status: str = PaperStatus.PRACTICE_AVAILABLE,
    exam_type: str = ExamType.PRACTICE,
    title: str | None = None,
    attempt_limit: int = 0,
    allow_retake: bool = True,
    show_answers_after_submit: bool = True,
    total_marks: int = 20,
    teacher: User | None = None,
    section: Section | None = None,
) -> Paper:
    subject = graph.subject(subject_code)
    visible = status in {PaperStatus.PUBLISHED, PaperStatus.PRACTICE_AVAILABLE}
    return Paper.objects.create(
        title=title or f"{subject.name} practice paper {graph.key}",
        exam_type=exam_type,
        subject=subject,
        class_room=graph.class_room,
        section=graph.section if section is None else section,
        campus=graph.campus,
        academic_year=graph.academic_year,
        teacher=teacher,
        total_marks=total_marks,
        duration_minutes=30,
        status=status,
        attempt_limit=attempt_limit,
        allow_retake=allow_retake,
        show_answers_after_submit=show_answers_after_submit,
        published_at=timezone.now() if visible else None,
    )


def add_question(
    paper: Paper,
    *,
    order: int,
    question_type: str = QuestionType.MCQ,
    marks: float = 1,
    correct_option: int | None = None,
    options: Sequence[str] | None = None,
    text: str | None = None,
    topic: str = "",
    chapter: str = "",
) -> PaperQuestion:
    if options is None:
        options = (
            ["True", "False"]
            if question_type == QuestionType.TRUE_FALSE
            else ["Statement A", "Statement B", "Statement C", "Statement D"]
        )
    return PaperQuestion.objects.create(
        paper=paper,
        order=order,
        question_type=question_type,
        text=text or f"Question {order} of {paper.title}",
        options=list(options),
        marks=marks,
        correct_option=correct_option,
        topic=topic,
        chapter=chapter,
    )


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------


def make_result(
    *,
    student: StudentProfile,
    subject: Subject,
    status: str = ResultStatus.PUBLISHED,
    total_marks: float = 50,
    obtained_marks: float = 40,
    assessment_name: str | None = None,
    assessment_type: str = ExamType.WEEKLY_TEST,
    days_ago: int = 10,
    paper: Paper | None = None,
    entered_by: User | None = None,
) -> Result:
    percentage = round(float(obtained_marks) / float(total_marks) * 100, 2)
    from assessment.services import grade_for

    return Result.objects.create(
        student=student,
        subject=subject,
        paper=paper,
        assessment_name=assessment_name or f"{subject.name} assessment",
        assessment_type=assessment_type,
        assessment_date=timezone.localdate() - timedelta(days=days_ago),
        total_marks=total_marks,
        obtained_marks=obtained_marks,
        percentage=percentage,
        grade=grade_for(percentage),
        status=status,
        entered_by=entered_by,
        published_at=timezone.now() if status == ResultStatus.PUBLISHED else None,
    )


def add_result_item(
    result: Result,
    *,
    topic: str = "Fundamentals",
    chapter: str = "Core concepts",
    marks_awarded: float = 6,
    marks_total: float = 10,
) -> ResultItem:
    return ResultItem.objects.create(
        result=result,
        question_label="Q1",
        chapter=chapter,
        topic=topic,
        marks_awarded=marks_awarded,
        marks_total=marks_total,
    )


# ---------------------------------------------------------------------------
# Attendance
# ---------------------------------------------------------------------------


def add_attendance(
    *,
    student: StudentProfile,
    subject: Subject,
    class_room: ClassRoom,
    status: str = AttendanceStatus.PRESENT,
    days_ago: int = 0,
) -> AttendanceRecord:
    return AttendanceRecord.objects.create(
        student=student,
        subject=subject,
        class_room=class_room,
        date=timezone.localdate() - timedelta(days=days_ago),
        status=status,
        period_label="P1",
    )
