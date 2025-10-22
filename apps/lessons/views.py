from datetime import date, datetime, time, timedelta, timezone as dt_timezone

from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.http import Http404
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.db.models import Count, Q

from apps.academics.models import Group, Subject
from apps.students.models import Student
from apps.workspaces.selectors import get_user_workspace

from .forms import GroupLessonCreateForm, IndividualLessonCreateForm, LessonRescheduleForm, AttendanceMarkForm
from .models import Lesson, LessonAttendance

from .selectors import get_workspace_lessons, get_lesson_attendance, get_calendar_lessons
from .services.creation import create_group_lesson, create_individual_lesson
from .services.rescheduling import reschedule_lesson
from .services.lifecycle import change_lesson_status
from .services.attendance import set_lesson_attendance

from .timezone_utils import get_calendar_timezone


def get_current_workspace(user):
    workspace = get_user_workspace(user)

    if workspace is None:
        raise Http404("Workspace not found.")
    
    return workspace


def add_service_errors(form, error):
    for message in error.messages:
        form.add_error(None, message)


@login_required
def individual_lesson_create_view(request):

    workspace = get_current_workspace(request.user)

    form = IndividualLessonCreateForm(
        request.POST or None,
        workspace=workspace
    )

    if request.method == "POST" and form.is_valid():

        try:
            lesson = create_individual_lesson(
                workspace=workspace,
                student_id=(
                    form.cleaned_data["student"].id
                ),
                subject_id=(
                    form.cleaned_data["subject"].id
                ),
                start_at=(
                    form.cleaned_data["start_at"]
                ),
                end_at=(
                    form.cleaned_data["end_at"]
                ),
                notes=(
                    form.cleaned_data["notes"]
                )
            )

        except ValidationError as error:
            add_service_errors(form, error)

        except IntegrityError:
            form.add_error(
                None,
                "This time interval is unavailable. "
                "Another lesson may already "
                "occupy the selected time."
            )

        except (
            Student.DoesNotExist,
            Subject.DoesNotExist
        ):
            form.add_error(
                None,
                "The selected student or subject "
                "is no longer available."
            )

        else:
            messages.success(
                request,
                "Individual lesson created successfully."
            )

            return redirect("lessons:lesson_detail", lesson_id=lesson.id)

    return render(request, "lessons/lesson_form.html",
        {
            "form": form,
            "page_title": "Schedule Individual Lesson",
            "timezone_name": (
                get_calendar_timezone().key
            )
        }
    )


@login_required
def group_lesson_create_view(request):

    workspace = get_current_workspace(request.user)

    form = GroupLessonCreateForm(
        request.POST or None,
        workspace=workspace
    )

    if request.method == "POST" and form.is_valid():

        try:
            lesson = create_group_lesson(
                workspace=workspace,
                group_id=(
                    form.cleaned_data["group"].id
                ),
                start_at=(
                    form.cleaned_data["start_at"]
                ),
                end_at=(
                    form.cleaned_data["end_at"]
                ),
                notes=(
                    form.cleaned_data["notes"]
                )
            )

        except ValidationError as error:
            add_service_errors(form, error)

        except IntegrityError:
            form.add_error(
                None,
                "This time interval is unavailable."
            )

        except Group.DoesNotExist:
            form.add_error(
                "group",
                "The selected group is no longer available."
            )

        else:
            messages.success(
                request,
                "Group lesson created successfully."
            )

            return redirect(
                "lessons:lesson_detail",
                lesson_id=lesson.id
            )

    return render(
        request,
        "lessons/lesson_form.html",
        {
            "form": form,
            "page_title": "Schedule Group Lesson",
            "timezone_name": (
                get_calendar_timezone().key
            ),
        }
    )


@login_required
def lesson_detail_view(request, lesson_id):

    workspace = get_current_workspace(request.user)

    lesson = get_object_or_404(
        get_workspace_lessons(
            workspace=workspace
        ),
        id=lesson_id
    )

    now = timezone.now()

    can_complete = (
        lesson.status == Lesson.Status.SCHEDULED
        and lesson.end_at <= now
    )

    can_cancel = (
        lesson.status == Lesson.Status.SCHEDULED
        and lesson.start_at > now
    )

    can_reschedule = can_cancel

    calendar_tz = get_calendar_timezone()

    return render(request, "lessons/lesson_detail.html",
        {
            "lesson": lesson,

            "start_local": timezone.localtime(
                lesson.start_at,
                calendar_tz
            ),

            "end_local": timezone.localtime(
                lesson.end_at,
                calendar_tz
            ),

            "timezone_name": calendar_tz.key,

            "can_complete": can_complete,
            "can_cancel": can_cancel,
            "can_reschedule": can_reschedule,
        }
    )


@login_required
def lesson_reschedule_view(request, lesson_id):
    workspace = get_current_workspace(request.user)

    lesson = get_object_or_404(
        get_workspace_lessons(
            workspace=workspace
        ),
        id=lesson_id
    )

    if lesson.status != Lesson.Status.SCHEDULED:
        messages.error(
            request,
            "Only scheduled lessons "
            "can be rescheduled."
        )

        return redirect("lessons:lesson_detail",
            lesson_id=lesson.id
        )

    calendar_tz = get_calendar_timezone()

    local_start = timezone.localtime(lesson.start_at, calendar_tz)

    local_end = timezone.localtime(lesson.end_at, calendar_tz)

    initial = {
        "start_date": local_start.date(),
        "start_time": local_start.time().replace(
            tzinfo=None
        ),

        "end_date": local_end.date(),
        "end_time": local_end.time().replace(
            tzinfo=None
        )
    }

    form = LessonRescheduleForm(
        request.POST or None,
        initial=initial
    )

    if request.method == "POST" and form.is_valid():

        try:
            updated_lesson = reschedule_lesson(
                workspace=workspace,
                lesson_id=lesson.id,
                start_at=form.cleaned_data["start_at"],
                end_at=form.cleaned_data["end_at"]
            )

        except ValidationError as error:
            add_service_errors(form, error)

        except IntegrityError:
            form.add_error(
                None,
                "Cannot reschedule the lesson. "
                "The selected time may already "
                "be occupied."
            )

        except Lesson.DoesNotExist:
            raise Http404("Lesson not found.")

        else:
            messages.success(
                request,
                "Lesson rescheduled successfully."
            )

            return redirect(
                "lessons:lesson_detail",
                lesson_id=updated_lesson.id
            )

    return render(request, "lessons/lesson_form.html",
        {
            "form": form,
            "page_title": "Reschedule Lesson",
            "timezone_name": calendar_tz.key
        }
    )


def get_day_boundaries(*, selected_date, calendar_tz):
    next_date = selected_date + timedelta(days=1,)

    day_start = datetime.combine(
        selected_date,
        time.min,
        tzinfo=calendar_tz
    )

    day_end = datetime.combine(
        next_date,
        time.min,
        tzinfo=calendar_tz
    )

    return (
        day_start.astimezone(dt_timezone.utc),
        day_end.astimezone(dt_timezone.utc)
    )


@login_required
def calendar_view(request):

    workspace = get_current_workspace(
        request.user
    )

    calendar_tz = get_calendar_timezone()

    calendar_mode = request.GET.get("view", "week")

    if calendar_mode not in {"day", "week"}:
        raise Http404(
            "Invalid calendar view."
        )

    raw_date = request.GET.get("date")

    if raw_date:
        try:
            selected_date = date.fromisoformat(raw_date)

        except ValueError:
            raise Http404("Invalid calendar date.")
        
    else:
        selected_date = timezone.localdate(
            timezone.now(),
            calendar_tz
        )

    if calendar_mode == "week":

        period_start_date = (
            selected_date - timedelta(days=selected_date.weekday()))

        period_end_date = (
            period_start_date + timedelta(days=7))

        previous_date = (
            period_start_date - timedelta(days=7))

        next_date = (
            period_start_date + timedelta(days=7))

    else:

        period_start_date = selected_date

        period_end_date = (
            selected_date + timedelta(days=1))

        previous_date = (
            selected_date - timedelta(days=1))

        next_date = (
            selected_date + timedelta(days=1))

    period_start, _ = get_day_boundaries(
        selected_date=period_start_date,
        calendar_tz=calendar_tz
    )

    period_end, _ = get_day_boundaries(
        selected_date=period_end_date,
        calendar_tz=calendar_tz
    )

    lessons = list(
        get_calendar_lessons(
            workspace=workspace,
            period_start=period_start,
            period_end=period_end
        )
    )

    lesson_entries = []

    for lesson in lessons:

        lesson_entries.append(
            {
                "lesson": lesson,

                "local_start": timezone.localtime(
                    lesson.start_at,
                    calendar_tz
                ),

                "local_end": timezone.localtime(
                    lesson.end_at,
                    calendar_tz
                )
            }
        )

    days = []

    current_date = period_start_date

    while current_date < period_end_date:

        day_start, day_end = get_day_boundaries(
            selected_date=current_date,
            calendar_tz=calendar_tz
        )

        day_entries = [
            entry
            for entry in lesson_entries
            if (
                entry["lesson"].start_at < day_end
                and entry["lesson"].end_at > day_start
            )
        ]

        days.append(
            {
                "date": current_date,
                "entries": day_entries
            }
        )

        current_date += timedelta(days=1)

    return render(request, "lessons/calendar.html",
        {
            "calendar_mode": calendar_mode,
            "selected_date": selected_date,
            "days": days,
            "previous_date": previous_date,
            "next_date": next_date,
            "timezone_name": calendar_tz.key
        }
    )


@login_required
@require_POST
def lesson_status_view(request, lesson_id, action):
    if action not in {"complete", "cancel"}:
        raise Http404(
            "Unknown lesson status action."
        )

    workspace = get_current_workspace(request.user)

    lesson = get_object_or_404(get_workspace_lessons(workspace=workspace), id=lesson_id)

    reason = ""

    if action == "cancel":
        reason = request.POST.get(
            "cancellation_reason",
            ""
        )

    try:
        change_lesson_status(
            workspace=workspace,
            lesson_id=lesson.id,
            action=action,
            reason=reason
        )

    except ValidationError as error:
        messages.error(
            request,
            error.messages[0]
        )

    except IntegrityError:
        messages.error(
            request,
            "The lesson could not be updated. "
            "Please check its current state."
        )

    except Lesson.DoesNotExist:
        raise Http404(
            "Lesson not found."
        )

    else:
        messages.success(
            request,
            "Lesson status updated successfully."
        )

    return redirect(
        "lessons:lesson_detail",
        lesson_id=lesson.id
    )


@login_required
def lesson_attendance_view(request, lesson_id):
    workspace = get_current_workspace(
        request.user
    )

    lesson = get_object_or_404(
        get_workspace_lessons(
            workspace=workspace
        ),
        id=lesson_id
    )

    is_ready = (
        lesson.status == Lesson.Status.COMPLETED
        and lesson.attendance_initialized_at is not None
    )

    is_legacy = (
        lesson.status == Lesson.Status.COMPLETED
        and lesson.attendance_initialized_at is None
    )

    entries = []

    stats = {
        "total": 0,
        "pending": 0,
        "present": 0,
        "absent": 0,
        "late": 0,
        "excused": 0
    }

    if is_ready:

        records = get_lesson_attendance(
            workspace=workspace,
            lesson=lesson
        )

        stats = records.aggregate(
            total=Count("id"),

            pending=Count(
                "id",
                filter=Q(status=LessonAttendance.Status.PENDING)
            ),

            present=Count(
                "id",
                filter=Q(status=LessonAttendance.Status.PRESENT)
            ),

            absent=Count(
                "id",
                filter=Q(status=LessonAttendance.Status.ABSENT)
            ),

            late=Count(
                "id",
                filter=Q(status=LessonAttendance.Status.LATE)
            ),

            excused=Count(
                "id",
                filter=Q(status=LessonAttendance.Status.EXCUSED)
            )
        )

        for attendance in records:

            initial_status = ""

            if attendance.status != LessonAttendance.Status.PENDING:
                initial_status = attendance.status

            entries.append(
                {
                    "attendance": attendance,

                    "form": AttendanceMarkForm(
                        initial={
                            "status": initial_status,
                            "notes": attendance.notes
                        }
                    )
                }
            )

    return render(request, "lessons/attendance.html",
        {
            "lesson": lesson,
            "entries": entries,
            "stats": stats,
            "is_ready": is_ready,
            "is_legacy": is_legacy
        },
    )


@login_required
@require_POST
def attendance_mark_view(request, lesson_id, attendance_id):
    workspace = get_current_workspace(request.user)

    lesson = get_object_or_404(
        get_workspace_lessons(
            workspace=workspace
        ),
        id=lesson_id
    )

    attendance = get_object_or_404(
        get_lesson_attendance(
            workspace=workspace,
            lesson=lesson
        ),
        id=attendance_id
    )

    form = AttendanceMarkForm(request.POST)

    if not form.is_valid():

        messages.error(
            request,
            "Invalid attendance data."
        )

    else:

        try:
            set_lesson_attendance(
                workspace=workspace,
                lesson_id=lesson.id,
                attendance_id=attendance.id,
                status=form.cleaned_data["status"],
                notes=form.cleaned_data["notes"],
                recorded_by=request.user
            )

        except ValidationError as error:
            messages.error(
                request,
                error.messages[0]
            )

        except (
            Lesson.DoesNotExist,
            LessonAttendance.DoesNotExist
        ):
            raise Http404(
                "Attendance record not found."
            )

        else:
            messages.success(
                request,
                "Attendance updated successfully."
            )

    return redirect(
        "lessons:attendance",
        lesson_id=lesson.id
    )