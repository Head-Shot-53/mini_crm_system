import uuid

from decimal import Decimal

import pytest

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from apps.students.models import Student
from apps.workspaces.models import Workspace

pytestmark = pytest.mark.django_db

@pytest.fixture
def workspace():
    User = get_user_model()

    user = User.objects.create_user(
        email="teacher@gmail.com",
        password="TestPassword123!"
    )

    return Workspace.objects.create(owner=user, name = "Test Workspace")

def test_create_student(workspace):
    student = Student.objects.create(
        workspace=workspace,
        first_name="Anna",
        last_name="Kowalska",
    )

    assert isinstance(student.id, uuid.UUID)

    assert student.full_name == "Anna Kowalska"

    assert student.status == Student.Status.ACTIVE

    assert student.workspace == workspace

def test_student_can_have_individual_price(workspace):
    student = Student.objects.create(
        workspace=workspace,
        first_name = "Oleg",
        last_name = "Ivanov",
        default_lesson_price = Decimal("120.00")
    )

    student.refresh_from_db()

    assert student.default_lesson_price == Decimal("120.00")

def test_student_price_cannot_be_negative(workspace):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Student.objects.create(
                workspace=workspace,
                first_name = "Maria",
                last_name = 'Nowak',
                default_lesson_price = Decimal("-50.00")
            )