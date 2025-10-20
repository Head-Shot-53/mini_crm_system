from datetime import timedelta

from zoneinfo import ZoneInfo

import pytest

from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model


from apps.students.models import Student
from apps.academics.models import Subject
from apps.workspaces.models import Workspace
from apps.lessons.models import Lesson
from apps.lessons.services.creation import create_individual_lesson


pytestmark = pytest.mark.django_db


def build_time_data(start_at, end_at):
    tz = ZoneInfo(settings.TIME_ZONE)

    local_start = timezone.localtime(start_at, tz)

    local_end = timezone.localtime(end_at, tz)

    return {
        "start_date": local_start.strftime("%Y-%m-%d"),

        "start_time": local_start.strftime("%H:%M"),

        "end_date": local_end.strftime("%Y-%m-%d"),

        "end_time": local_end.strftime("%H:%M")
    }


def test_create_individual_lesson_view(client, workspace, student, subject, enrollment, lesson_time):
    client.force_login(workspace.owner)

    start_at, end_at = lesson_time

    data = build_time_data(start_at, end_at)

    data.update(
        {
            "student": str(student.id),
            "subject": str(subject.id),
            "notes": "Python fundamentals."
        }
    )

    response = client.post(
        reverse("lessons:create_individual"),
        data
    )

    assert response.status_code == 302

    lesson = Lesson.objects.get(workspace=workspace)

    assert lesson.student == student
    assert lesson.subject == subject
    assert lesson.group is None

    assert lesson.notes == ("Python fundamentals.")


def test_create_lesson_view_rejects_overlap(client, workspace, student, subject, enrollment, lesson_time):
    start_at, end_at = lesson_time

    create_individual_lesson(
        workspace=workspace,
        student_id=student.id,
        subject_id=subject.id,
        start_at=start_at,
        end_at=end_at
    )

    client.force_login(
        workspace.owner
    )

    data = build_time_data(
        start_at + timedelta(minutes=30),
        end_at + timedelta(minutes=30)
    )

    data.update(
        {
            "student": str(student.id),
            "subject": str(subject.id)
        }
    )

    response = client.post(reverse("lessons:create_individual"), data)

    assert response.status_code == 200

    assert response.context["form"].non_field_errors()

    assert Lesson.objects.count() == 1


@pytest.mark.parametrize(
    "view_name",
    [
        "lessons:calendar",
        "lessons:create_individual",
        "lessons:create_group"
    ]
)
def test_lesson_pages_require_authentication(client, view_name):
    response = client.get(reverse(view_name))

    assert response.status_code == 302


def test_daily_calendar_displays_lesson(client, workspace, student, subject, enrollment, lesson_time):
    start_at, end_at = lesson_time

    lesson = create_individual_lesson(
        workspace=workspace,
        student_id=student.id,
        subject_id=subject.id,
        start_at=start_at,
        end_at=end_at
    )

    local_date = timezone.localtime(
        start_at,
        ZoneInfo(settings.TIME_ZONE)
    ).date()

    client.force_login(workspace.owner)

    response = client.get(
        reverse("lessons:calendar"),
        {
            "view": "day",
            "date": local_date.isoformat()
        }
    )

    assert response.status_code == 200

    days = response.context["days"]

    assert len(days) == 1

    lesson_ids = [
        entry["lesson"].id
        for entry in days[0]["entries"]
    ]

    assert lesson.id in lesson_ids


def test_weekly_calendar_has_seven_days(client, workspace):
    client.force_login(workspace.owner)

    response = client.get(
        reverse("lessons:calendar"),
        {
            "view": "week"
        }
    )

    assert response.status_code == 200

    days = response.context["days"]

    assert len(days) == 7

    assert days[0]["date"].weekday() == 0

    assert days[6]["date"].weekday() == 6


def test_calendar_rejects_invalid_date(client, workspace):
    client.force_login(workspace.owner)

    response = client.get(
        reverse("lessons:calendar"),
        {
            "view": "week",
            "date": "invalid-date"
        }
    )

    assert response.status_code == 404


def test_reschedule_lesson_view(client, workspace, student, subject, enrollment, lesson_time):
    start_at, end_at = lesson_time

    lesson = create_individual_lesson(
        workspace=workspace,
        student_id=student.id,
        subject_id=subject.id,
        start_at=start_at,
        end_at=end_at
    )

    new_start = start_at + timedelta(hours=2)

    new_end = new_start + timedelta(hours=1)

    client.force_login(workspace.owner)

    response = client.post(
        reverse(
            "lessons:reschedule",
            kwargs={
                "lesson_id": lesson.id
            }
        ),
        build_time_data(new_start, new_end)
    )

    assert response.status_code == 302

    lesson.refresh_from_db()

    assert lesson.start_at == new_start
    assert lesson.end_at == new_end


def test_cannot_access_foreign_lesson(client, workspace, lesson_time):
    User = get_user_model()

    foreign_teacher = User.objects.create_user(
        email="foreign@example.com",
        password="TestPassword123!"
    )

    foreign_workspace = Workspace.objects.create(
        owner=foreign_teacher,
        name="Foreign Workspace"
    )

    foreign_student = Student.objects.create(
        workspace=foreign_workspace,
        first_name="Maria",
        last_name="Nowak"
    )

    foreign_subject = Subject.objects.create(
        workspace=foreign_workspace,
        name="English"
    )

    start_at, end_at = lesson_time

    foreign_lesson = Lesson.objects.create(
        workspace=foreign_workspace,
        student=foreign_student,
        subject=foreign_subject,
        start_at=start_at,
        end_at=end_at
    )

    client.force_login(workspace.owner)

    detail_url = reverse(
        "lessons:lesson_detail",
        kwargs={
            "lesson_id": foreign_lesson.id
        }
    )

    response = client.get(detail_url)

    assert response.status_code == 404

    reschedule_url = reverse(
        "lessons:reschedule",
        kwargs={
            "lesson_id": foreign_lesson.id
        }
    )

    response = client.post(
        reschedule_url,
        build_time_data(
            start_at + timedelta(hours=2),
            end_at + timedelta(hours=2)
        )
    )

    assert response.status_code == 404

    foreign_lesson.refresh_from_db()

    assert foreign_lesson.start_at == start_at