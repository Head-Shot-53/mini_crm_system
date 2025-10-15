import pytest

from apps.lessons.selectors import get_workspace_lessons

from apps.lessons.services.creation import create_individual_lesson


pytestmark = pytest.mark.django_db


def test_workspace_lesson_selector(workspace, student, subject, enrollment, lesson_time):
    start_at, end_at = lesson_time

    lesson = create_individual_lesson(
        workspace=workspace,
        student_id=student.id,
        subject_id=subject.id,
        start_at=start_at,
        end_at=end_at
    )

    lessons = list(
        get_workspace_lessons(workspace=workspace))

    assert lessons == [lesson]