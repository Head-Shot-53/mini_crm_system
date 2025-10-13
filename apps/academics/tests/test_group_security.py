import pytest

from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import reverse

from apps.workspaces.models import Workspace

from apps.academics.models import Group, Subject

from apps.academics.selectors import  get_workspace_groups_with_counts


@pytest.fixture
def teacher(db, django_user_model):
    return django_user_model.objects.create_user(
        email="teacher@example.com",
        password="TestPassword123!"
    )


@pytest.fixture
def workspace(db, teacher):
    return Workspace.objects.create(
        owner=teacher,
        name="Test Teaching"
    )


@pytest.fixture
def foreign_teacher(db, django_user_model):
    return django_user_model.objects.create_user(
        email="foreign@example.com",
        password="TestPassword123!"
    )


@pytest.fixture
def foreign_workspace(db, foreign_teacher):
    return Workspace.objects.create(
        owner=foreign_teacher,
        name="Foreign Workspace"
    )


@pytest.mark.django_db
def test_foreign_subject_is_not_exposed(client, teacher, workspace, foreign_workspace):

    foreign_subject = Subject.objects.create(
        workspace=foreign_workspace,
        name="Foreign Subject"
    )

    invalid_group = Group.objects.create(
        workspace=workspace,
        subject=foreign_subject,
        name="Invalid Group"
    )

    groups = get_workspace_groups_with_counts(
        workspace=workspace
    )

    assert not groups.filter(
        id=invalid_group.id,
    ).exists()

    client.force_login(teacher)

    response = client.get(
        reverse(
            "academics:group_detail",
            kwargs={
                "group_id": invalid_group.id
            }
        )
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_tenant_audit_detects_invalid_group(workspace, foreign_workspace):

    foreign_subject = Subject.objects.create(
        workspace=foreign_workspace,
        name="Foreign Subject"
    )

    Group.objects.create(
        workspace=workspace,
        subject=foreign_subject,
        name="Invalid Group"
    )

    with pytest.raises(CommandError):
        call_command(
            "audit_tenant_relations"
        )