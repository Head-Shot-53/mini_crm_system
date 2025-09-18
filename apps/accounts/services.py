from django.db import transaction

from apps.workspaces.services import create_personal_workspace

from .models import TeacherProfile, User

@transaction.atomic
def register_teacher(*, email, password, first_name='', last_name='', workspace_name=None):
    user = User.objects.create_user(email=email, password=password, first_name=first_name, last_name=last_name)

    TeacherProfile.objects.create(user=user)

    create_personal_workspace(owner=user, name=workspace_name)

    return user