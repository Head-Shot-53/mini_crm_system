from django.db import transaction

from apps.workspaces.services import create_personal_workspace

from .models import TeacherProfile, User

@transaction.atomic
def register_teacher(*, email, password, first_name='', last_name='', workspace_name=None):
    user = User.objects.create_user(email=email, password=password, first_name=first_name, last_name=last_name)

    TeacherProfile.objects.create(user=user)

    create_personal_workspace(owner=user, name=workspace_name)

    return user

@transaction.atomic
def update_teacher_settings(*, user_form, profile_form, workspace_form):
    user = user_form.save()
    profile = profile_form.save()
    workspace = workspace_form.save()

    return user, profile, workspace