"""
End-to-end smoke test against a running API.

    python tools/smoke.py

Exercises the real HTTP surface: login, dashboard, timetable, papers, the
practice engine, results, attendance, announcements, requests and the
permission boundary between two different students.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar

BASE = "http://127.0.0.1:8000"
PASSWORD = "TelPortal@2026"

passed: list[str] = []
failed: list[tuple[str, str]] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        passed.append(label)
        print(f"  PASS  {label}")
    else:
        failed.append((label, detail))
        print(f"  FAIL  {label} :: {detail}")


class Client:
    def __init__(self) -> None:
        self.jar = CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar),
            urllib.request.HTTPRedirectHandler(),
        )

    def request(self, method: str, path: str, body=None, headers: dict | None = None):
        url = f"{BASE}{path}"
        data = None
        request_headers = {"Accept": "application/json", "User-Agent": "TEL-smoke/1.0"}
        if body is not None:
            data = json.dumps(body).encode()
            request_headers["Content-Type"] = "application/json"
        if headers:
            request_headers.update(headers)
        request = urllib.request.Request(url, data=data, headers=request_headers, method=method)
        try:
            with self.opener.open(request) as response:
                raw = response.read().decode()
                return response.status, (json.loads(raw) if raw else {})
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode()
            try:
                return exc.code, json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                return exc.code, {"raw": raw[:300]}

    def get(self, path, **kw):
        return self.request("GET", path, **kw)

    def post(self, path, body=None, **kw):
        """POSTs always echo the CSRF cookie, exactly as the SPA does."""

        headers = dict(kw.pop("headers", {}) or {})
        if "X-TEL-CSRFToken" not in headers:
            headers.update(csrf_headers(self))
        return self.request("POST", path, body=body, headers=headers, **kw)


def csrf_headers(client: Client) -> dict:
    client.get("/api/auth/csrf/")
    for cookie in client.jar:
        if cookie.name == "tel_csrftoken":
            return {"X-TEL-CSRFToken": cookie.value}
    return {}


def login(email: str) -> Client:
    client = Client()
    headers = csrf_headers(client)
    status, _ = client.post(
        "/api/auth/login/", {"email": email, "password": PASSWORD}, headers=headers
    )
    if status != 200:
        raise SystemExit(f"Could not sign in as {email} (HTTP {status}). Run `manage.py seed_demo` first.")
    return client


def main() -> int:
    print("\nTEL Student Portal — API smoke test\n")

    print("Health")
    anon = Client()
    status, payload = anon.get("/api/health/")
    check("health endpoint responds", status == 200 and payload.get("status") == "ok", str(payload))

    print("\nAuthentication")
    status, payload = anon.post(
        "/api/auth/login/", {"email": "nobody@tel.edu.pk", "password": "wrong-password"}
    )
    check("rejects bad credentials", status == 400, f"HTTP {status}")

    status, payload = anon.get("/api/dashboard/")
    check("dashboard requires auth", status == 401, f"HTTP {status}")

    admin = login("admin@tel.edu.pk")
    status, payload = admin.get("/api/auth/me/")
    check("admin session established", status == 200 and payload["user"]["role"] == "ADMIN", str(status))

    students = []
    status, payload = admin.get("/api/manage/students/?page_size=1")
    check("staff register reachable", status == 200, f"HTTP {status}")
    if status == 200:
        for row in admin.get("/api/manage/students/")[1]["results"][:6]:
            students.append(row["id"])
    check("seeded students exist", len(students) >= 2, f"found {len(students)}")

    # Find two real student logins from the seed.
    import os
    import sys as _sys

    backend = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    _sys.path.insert(0, os.path.abspath(backend))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "telportal.settings")
    import django

    django.setup()
    from accounts.models import StudentProfile

    profiles = list(
        StudentProfile.objects.select_related("user", "class_room", "section").order_by("student_code")
    )
    check("seed produced students", len(profiles) >= 2, f"{len(profiles)}")
    if len(profiles) < 2:
        return 1

    student_a = login(profiles[0].user.email)
    student_b = login(profiles[-1].user.email)

    print("\nDashboard")
    status, dashboard = student_a.get("/api/dashboard/")
    check("dashboard loads", status == 200 and "identity" in dashboard, f"HTTP {status}")
    if status == 200:
        identity = dashboard["identity"]
        check("identity comes from the database", identity["full_name"] == profiles[0].user.full_name, str(identity))
        check("greeting is present", bool(identity["greeting"]), str(identity.get("greeting")))
        check(
            "attendance is real data",
            dashboard["attendance"]["available"] is True
            and dashboard["attendance"]["overall_percentage"] is not None,
            str(dashboard["attendance"])[:160],
        )
        check(
            "subject performance is computed",
            dashboard["performance"]["available"] is True
            and len(dashboard["performance"]["subjects"]) > 0,
            str(dashboard["performance"])[:160],
        )

    print("\nTimetable")
    status, payload = student_a.get("/api/timetable/")
    check("timetable loads", status == 200, f"HTTP {status}")
    if status == 200 and payload.get("timetable"):
        check("only published timetable is served", payload["timetable"]["status"] == "PUBLISHED", str(payload["timetable"]["status"]))
        check("timetable has entries", len(payload["timetable"]["entries"]) > 0, "no entries")
    status, payload = student_a.get("/api/timetable/today/")
    check("today view loads", status == 200 and "today" in payload, f"HTTP {status}")

    print("\nPapers and practice")
    status, papers = student_a.get("/api/student/papers/")
    check("paper archive loads", status == 200 and papers["count"] > 0, f"HTTP {status} {str(papers)[:120]}")
    practice = next(
        (p for p in papers.get("results", []) if p["can_practice"]), None
    )
    check("a practice paper is available", practice is not None, "none found")

    if practice:
        status, session = student_a.post(f"/api/papers/{practice['id']}/practice/")
        check("practice session starts", status == 200 and "questions" in session, f"HTTP {status}")
        if status == 200:
            check(
                "answer key is not exposed before submission",
                all("correct_option" not in q for q in session["questions"]),
                "leaked",
            )
            answers = [
                {"question_id": q["id"], "selected_option": (q.get("options") and 0) or None}
                for q in session["questions"]
                if q.get("options")
            ]
            attempt_id = session["attempt_id"]
            headers = csrf_headers(student_a)
            status, _ = student_a.post(
                f"/api/practice/{attempt_id}/save/", {"answers": answers}, headers=headers
            )
            check("progress saves", status == 200, f"HTTP {status}")
            status, result = student_a.post(f"/api/practice/{attempt_id}/submit/", {}, headers=headers)
            check("attempt submits and scores", status == 200 and "percentage" in result, f"HTTP {status}")
            if status == 200:
                check(
                    "score is within range",
                    0 <= result["score"] <= result["total_marks"],
                    f"{result['score']}/{result['total_marks']}",
                )
            status, review = student_a.get(f"/api/practice/{attempt_id}/review/")
            check("answer key unlocks after submission", status == 200, f"HTTP {status}")

    print("\nResults and analytics")
    status, results = student_a.get("/api/student/results/")
    check("results load", status == 200 and results["count"] > 0, f"HTTP {status} {str(results)[:120]}")
    if status == 200:
        check(
            "only published results are visible",
            all(r["status"] == "PUBLISHED" for r in results["results"]),
            "unpublished leaked",
        )
    status, analytics = student_a.get("/api/student/analytics/")
    check("analytics load", status == 200, f"HTTP {status}")
    if status == 200:
        check(
            "weak subjects are explained",
            all(w.get("reason") for w in analytics["weak_subjects"]),
            "missing reason",
        )
    status, topics = student_a.get("/api/student/analytics/topics/")
    check(
        "topic analysis is honest about availability",
        status == 200 and ("available" in topics),
        f"HTTP {status}",
    )

    print("\nAttendance")
    status, payload = student_a.get("/api/student/attendance/")
    check("attendance loads", status == 200 and payload["available"] is True, f"HTTP {status}")

    print("\nEngagement")
    for path, label in (
        ("/api/student/assignments/", "assignments"),
        ("/api/student/resources/", "resources"),
        ("/api/student/announcements/", "announcements"),
        ("/api/student/calendar/", "calendar"),
        ("/api/student/practice-history/", "practice history"),
        ("/api/student/requests/", "requests"),
        ("/api/notifications/", "notifications"),
    ):
        status, payload = student_a.get(path)
        check(f"{label} load", status == 200, f"HTTP {status}")

    headers = csrf_headers(student_a)
    status, ticket = student_a.post(
        "/api/student/requests/",
        {
            "request_type": "OTHER",
            "subject_line": "Smoke test ticket",
            "description": "Created by the automated smoke test to verify the request pipeline.",
        },
        headers=headers,
    )
    check("student can submit a request", status == 201 and ticket.get("ticket_id", "").startswith("TEL-"), f"HTTP {status} {str(ticket)[:160]}")

    status, payload = student_a.post(
        "/api/student/feedback/",
        {"category": "PORTAL", "rating": 5, "message": "Smoke test feedback entry for the portal."},
        headers=headers,
    )
    check("student can submit feedback", status == 201, f"HTTP {status}")

    print("\nPermissions")
    status, payload = student_a.get("/api/manage/results/")
    check("student cannot open the result register", status == 403, f"HTTP {status}")
    status, payload = student_a.get("/api/manage/papers/")
    check("student cannot open the paper register", status == 403, f"HTTP {status}")
    status, payload = student_a.get("/api/audit-log/")
    check("student cannot read the audit log", status == 403, f"HTTP {status}")
    status, payload = admin.get("/api/audit-log/?limit=5")
    check("staff can read the audit log", status == 200, f"HTTP {status}")

    if practice:
        status, _ = student_b.get(f"/api/papers/{practice['id']}/")
        check("another student in a different class cannot read the paper", status == 404, f"HTTP {status}")

    # ID manipulation: student B must never reach student A's attempt.
    from assessment.models import PracticeAttempt

    attempt = PracticeAttempt.objects.filter(
        student=profiles[0], status="GRADED"
    ).first()
    if attempt:
        headers_b = csrf_headers(student_b)
        status, _ = student_b.get(f"/api/practice/{attempt.id}/review/")
        check("cross-student attempt access is blocked", status == 404, f"HTTP {status}")
        status, _ = student_b.post(f"/api/practice/{attempt.id}/submit/", {}, headers=headers_b)
        check("cross-student submit is blocked", status == 404, f"HTTP {status}")

    print("\nFilters and search")
    status, filtered = student_a.get("/api/student/papers/?search=Physics")
    check("paper search filters server-side", status == 200, f"HTTP {status}")
    if status == 200:
        check(
            "search results are relevant",
            all("physics" in (p["title"] + p["subject_name"]).lower() for p in filtered["results"]),
            str([p["title"] for p in filtered["results"]][:3]),
        )
    status, filtered = student_a.get("/api/student/papers/?type=MONTHLY_TEST")
    check("paper type filter works", status == 200, f"HTTP {status}")
    if status == 200 and filtered["results"]:
        check(
            "type filter is honoured",
            all(p["exam_type"] == "MONTHLY_TEST" for p in filtered["results"]),
            "mismatch",
        )

    print("\nIntegration layer")
    status, payload = student_a.get("/api/integration/status/")
    check("integration status is reported", status == 200 and "mode" in payload, f"HTTP {status}")

    print(f"\n{len(passed)} passed, {len(failed)} failed\n")
    for label, detail in failed:
        print(f"  FAILED: {label} :: {detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
