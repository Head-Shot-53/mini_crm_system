from django.core.management.base import BaseCommand, CommandError

from django.db.models import F

from apps.academics.models import Group, GroupMembership, StudentSubject


class Command(BaseCommand):
    help = "Audit cross-workspace academic relationships."

    def handle(self, *args, **options):

        invalid_groups = (
            Group.objects
            .exclude(
                workspace_id=F(
                    "subject__workspace_id"
                )
            )
        )

        invalid_enrollments = (
            StudentSubject.objects
            .exclude(
                student__workspace_id=F(
                    "subject__workspace_id"
                )
            )
        )

        invalid_memberships = (
            GroupMembership.objects
            .exclude(
                group__workspace_id=F(
                    "student__workspace_id"
                )
            )
        )

        checks = {
            "Invalid Groups": invalid_groups,
            "Invalid StudentSubjects": invalid_enrollments,
            "Invalid GroupMemberships": invalid_memberships
        }

        has_errors = False

        for label, queryset in checks.items():

            identifiers = list(
                queryset.values_list(
                    "id",
                    flat=True
                )
            )

            self.stdout.write(f"{label}: {len(identifiers)}")

            if identifiers:
                has_errors = True

                for identifier in identifiers:
                    self.stdout.write(f"  - {identifier}")

        if has_errors:
            raise CommandError(
                "Tenant integrity violations detected."
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Tenant relationship audit passed."
            )
        )