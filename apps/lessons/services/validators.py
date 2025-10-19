from datetime import datetime

from django.core.exceptions import ValidationError
from django.utils import timezone


def validate_lesson_time(*, start_at, end_at):
    if not isinstance(start_at, datetime):
        raise ValidationError(
            "Lesson start must be a datetime."
        )

    if not isinstance(end_at, datetime):
        raise ValidationError(
            "Lesson end must be a datetime."
        )

    if timezone.is_naive(start_at):
        raise ValidationError(
            "Lesson start must be timezone-aware."
        )

    if timezone.is_naive(end_at):
        raise ValidationError(
            "Lesson end must be timezone-aware."
        )

    if end_at <= start_at:
        raise ValidationError(
            "Lesson end must be later than start."
        )

    if start_at <= timezone.now():
        raise ValidationError(
            "New lesson time must be in the future."
        )