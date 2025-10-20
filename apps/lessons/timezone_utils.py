from datetime import datetime, timezone as dt_timezone

from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.exceptions import ValidationError


def get_calendar_timezone():
    return ZoneInfo(settings.TIME_ZONE)


def resolve_local_datetime(*, lesson_date, lesson_time):
    tz = get_calendar_timezone()

    naive = datetime.combine(
        lesson_date,
        lesson_time
    )

    possible_datetimes = set()

    for fold in (0, 1):

        local_dt = naive.replace(
            tzinfo=tz,
            fold=fold
        )

        utc_dt = local_dt.astimezone(
            dt_timezone.utc
        )

        restored = (
            utc_dt
            .astimezone(tz)
            .replace(tzinfo=None)
        )

        if restored == naive:
            possible_datetimes.add(utc_dt)

    if not possible_datetimes:
        raise ValidationError(
            "This local time does not exist "
            "in the selected time zone."
        )

    if len(possible_datetimes) > 1:
        raise ValidationError(
            "This local time is ambiguous "
            "because of a daylight saving "
            "time transition."
        )

    return possible_datetimes.pop()