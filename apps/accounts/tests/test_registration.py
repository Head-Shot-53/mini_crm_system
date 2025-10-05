from unittest.mock import patch

import pytest

from django.contrib.auth import get_user_model

from apps.accounts.models import TeacherProfile
from apps.accounts.services import register_teacher


@pytest.mark.django_db
def test_registration_rolls_back_when_workspace_fails():
    User = get_user_model()

    email = "rollback@example.com"

    with patch(
        "apps.accounts.services.create_personal_workspace",
        side_effect=RuntimeError(
            "Simulated workspace creation failure"
        )
    ):
        with pytest.raises(RuntimeError):
            register_teacher(
                email=email,
                password="TestPassword123!",
                first_name="Test",
                last_name="Teacher"
            )

    assert not User.objects.filter(
        email=email,
    ).exists()

    assert not TeacherProfile.objects.filter(
        user__email=email
    ).exists()