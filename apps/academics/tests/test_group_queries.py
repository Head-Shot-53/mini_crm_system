import pytest

from django.contrib.auth import get_user_model

from apps.academics.models import Group, Subject

from apps.academics.selectors import get_workspace_groups_with_counts

from apps.workspaces.models import Workspace


@pytest.mark.django_db
def test_group_selector_avoids_n_plus_one(django_assert_num_queries):

    User = get_user_model()

    teacher = User.objects.create_user(
        email="teacher@example.com",
        password="TestPassword123!"
    )

    workspace = Workspace.objects.create(
        owner=teacher,
        name="Test Workspace"
    )

    subject = Subject.objects.create(
        workspace=workspace,
        name="Python"
    )

    for index in range(20):

        Group.objects.create(
            workspace=workspace,
            subject=subject,
            name=f"Python Group {index}"
        )

    with django_assert_num_queries(1):

        groups = list(
            get_workspace_groups_with_counts(workspace=workspace))

        for group in groups:
            _ = group.subject.name
            _ = group.active_members_count

    assert len(groups) == 20