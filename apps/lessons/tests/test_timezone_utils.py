from datetime import date, time

import pytest

from django.core.exceptions import ValidationError
from django.test import override_settings

from apps.lessons.timezone_utils import resolve_local_datetime


@override_settings(TIME_ZONE="Europe/Warsaw")
def test_resolve_polish_local_time():

    result = resolve_local_datetime(
        lesson_date=date(2026, 10, 5),
        lesson_time=time(16, 0)
    )

    assert result.hour == 14


@override_settings(TIME_ZONE="Europe/Warsaw")
def test_reject_nonexistent_local_time():

    with pytest.raises(ValidationError):

        resolve_local_datetime(
            lesson_date=date(2026, 3, 29),
            lesson_time=time(2, 30)
        )


@override_settings(TIME_ZONE="Europe/Warsaw")
def test_reject_ambiguous_local_time():

    with pytest.raises(ValidationError):

        resolve_local_datetime(
            lesson_date=date(2026, 10, 25),
            lesson_time=time(2, 30)
        )