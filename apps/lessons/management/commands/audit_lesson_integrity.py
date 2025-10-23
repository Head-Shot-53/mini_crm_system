from django.core.management.base import BaseCommand, CommandError

from django.db.models import F

from apps.lessons.models import Lesson, LessonAttendance


class Command(BaseCommand):
    help = "Audit Lesson and Attendance data integrity."

    def handle(self, *args, **options):

        checks = {
            "Lesson subject workspace mismatch": (
                Lesson.objects.exclude(
                    subject__workspace_id=F("workspace_id")
                )
            ),

            "Lesson student workspace mismatch": (
                Lesson.objects
                .filter(student__isnull=False)
                .exclude(
                    student__workspace_id=F("workspace_id")
                )
            ),

            "Lesson group workspace mismatch": (
                Lesson.objects
                .filter(group__isnull=False)
                .exclude(
                    group__workspace_id=F("workspace_id")
                )
            ),

            "Lesson group subject mismatch": (
                Lesson.objects
                .filter(group__isnull=False)
                .exclude(
                    group__subject_id=F("subject_id")
                )
            ),

            "Attendance student workspace mismatch": (
                LessonAttendance.objects.exclude(
                    student__workspace_id=F(
                        "lesson__workspace_id"
                    )
                )
            ),

            "Attendance recorded by non-owner": (
                LessonAttendance.objects
                .filter(recorded_by__isnull=False)
                .exclude(
                    recorded_by_id=F(
                        "lesson__workspace__owner_id"
                    )
                )
            ),

            "Individual attendance student mismatch": (
                LessonAttendance.objects
                .filter(lesson__student__isnull=False)
                .exclude(
                    student_id=F("lesson__student_id")
                )
            ),

            "Individual attendance has membership": (
                LessonAttendance.objects.filter(
                    lesson__student__isnull=False,
                    group_membership__isnull=False
                )
            ),

            "Group attendance missing membership": (
                LessonAttendance.objects.filter(
                    lesson__group__isnull=False,
                    group_membership__isnull=True
                )
            ),

            "Group attendance membership group mismatch": (
                LessonAttendance.objects
                .filter(
                    lesson__group__isnull=False,
                    group_membership__isnull=False
                )
                .exclude(
                    group_membership__group_id=F(
                        "lesson__group_id"
                    )
                )
            ),

            "Group attendance membership student mismatch": (
                LessonAttendance.objects
                .filter(
                    lesson__group__isnull=False,
                    group_membership__isnull=False
                )
                .exclude(
                    group_membership__student_id=F(
                        "student_id"
                    )
                )
            ),

            "Attendance exists without initialization": (
                LessonAttendance.objects.filter(
                    lesson__attendance_initialized_at__isnull=True
                )
            )
        }

        has_errors = False

        for label, queryset in checks.items():
            count = queryset.count()

            self.stdout.write(f"{label}: {count}")

            if count:
                has_errors = True

                for identifier in queryset.values_list("id", flat=True)[:10]:
                    self.stdout.write(f"  - {identifier}")

        if has_errors:
            raise CommandError(
                "Lesson integrity violations detected."
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Lesson integrity audit passed."
            )
        )