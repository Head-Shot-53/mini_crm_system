import pytest

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.academics.models import Group, Subject
from apps.academics.services import create_group
from apps.academics.selectors import get_workspace_groups
from apps.workspaces.models import Workspace


pytestmark = pytest.mark.django_db


@pytest.fixture
def workspace():
    User = get_user_model()

    teacher = User.objects.create_user(
        email="teacher@example.com",
        password="TestPassword123!"
    )

    return Workspace.objects.create(owner=teacher, name="Test Teaching")


@pytest.fixture
def subject(workspace):
    return Subject.objects.create(workspace=workspace, name="Python")


def test_create_group(workspace, subject):

    group = create_group(
        workspace=workspace,
        subject_id=subject.id,
        name="Python Beginners",
        max_students=8
    )

    assert group.workspace == workspace

    assert group.subject == subject

    assert group.name == "Python Beginners"

    assert group.max_students == 8

    assert group.is_active is True


def test_group_name_is_normalized(workspace, subject):
    group = create_group(
        workspace=workspace,
        subject_id=subject.id,
        name="  Python Beginners  "
    )

    assert group.name == "Python Beginners"


def test_duplicate_group_name_is_rejected(workspace, subject):
    create_group(
        workspace=workspace,
        subject_id=subject.id,
        name="Python Beginners"
    )

    with pytest.raises(ValidationError):
        create_group(
            workspace=workspace,
            subject_id=subject.id,
            name="python beginners"
        )


def test_database_prevents_duplicate_groups(workspace, subject):
    Group.objects.create(
        workspace=workspace,
        subject=subject,
        name="Python Beginners"
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Group.objects.create(
                workspace=workspace,
                subject=subject,
                name=" PYTHON BEGINNERS "
            )


def test_cannot_create_group_with_foreign_subject(workspace):
    User = get_user_model()

    another_teacher = User.objects.create_user(
        email="another@example.com",
        password="TestPassword123!"
    )

    another_workspace = Workspace.objects.create(
        owner=another_teacher,
        name="Another Workspace"
    )

    foreign_subject = Subject.objects.create(
        workspace=another_workspace,
        name="English"
    )

    with pytest.raises(Subject.DoesNotExist):
        create_group(
            workspace=workspace,
            subject_id=foreign_subject.id,
            name="English A1"
        )

    assert Group.objects.count() == 0


def test_group_model_rejects_foreign_subject(workspace):
    User = get_user_model()

    another_teacher = User.objects.create_user(
        email="third@example.com",
        password="TestPassword123!"
    )

    another_workspace = Workspace.objects.create(
        owner=another_teacher,
        name="Third Workspace"
    )

    foreign_subject = Subject.objects.create(
        workspace=another_workspace,
        name="SQL"
    )

    group = Group(
        workspace=workspace,
        subject=foreign_subject,
        name="SQL Beginners"
    )

    with pytest.raises(ValidationError):
        group.full_clean()


def test_group_capacity_cannot_be_zero(workspace, subject):
    with pytest.raises(ValidationError):
        create_group(
            workspace=workspace,
            subject_id=subject.id,
            name="Python Advanced",
            max_students=0
        )


def test_database_rejects_zero_capacity(workspace, subject):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Group.objects.create(
                workspace=workspace,
                subject=subject,
                name="Python Advanced",
                max_students=0
            )


def test_group_selector_returns_only_own_groups(workspace, subject):
    own_group = create_group(
        workspace=workspace,
        subject_id=subject.id,
        name="Python Beginners"
    )

    User = get_user_model()

    another_teacher = User.objects.create_user(
        email="fourth@example.com",
        password="TestPassword123!"
    )

    another_workspace = Workspace.objects.create(
        owner=another_teacher,
        name="Another Workspace"
    )

    foreign_subject = Subject.objects.create(
        workspace=another_workspace,
        name="English"
    )

    Group.objects.create(
        workspace=another_workspace,
        subject=foreign_subject,
        name="English A1"
    )

    results = list(
        get_workspace_groups(
            workspace=workspace
        )
    )

    assert results == [own_group]