from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages

from apps.workspaces.forms import WorkspaceSettingsForm

from .forms import TeacherRegistrationForm, TeacherProfileForm, UserProfileForm
from .services import register_teacher, update_teacher_settings

def register_view(request):
    if request.user.is_authenticated:
        return redirect("accounts:profile")

    form = TeacherRegistrationForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        password = form.cleaned_data['password1']

        user = register_teacher(
            email=form.cleaned_data['email'],
            password=password,
            first_name=form.cleaned_data['first_name'],
            last_name=form.cleaned_data['last_name'],
            workspace_name=form.cleaned_data['workspace_name'] or None
        )

        authenticated_user = authenticate(request, email=user.email, password=password)

        if authenticated_user is not None:
            login(request, authenticated_user)

            return redirect("accounts:profile")
        return redirect("accounts:login")
    return render(request, "accounts/register.html", {'form' : form})

@login_required
def profile_view(request):
    workspace = (request.user.owned_workspaces.first())

    return render(request, "accounts/profile.html", {'workspace' : workspace})

@login_required
def profile_edit_view(request):
    workspace = request.user.owned_workspaces.first()

    if workspace is None:
        messages.error(request, "Your account does not have a workspace.")
        return redirect("accounts:profile")

    user_form = UserProfileForm(request.POST or None, instance=request.user, prefix="user")

    profile_form = TeacherProfileForm(
            request.POST or None,
            request.FILES or None,
            instance=request.user.teacher_profile,
            prefix="profile",
        )
    
    workspace_form = WorkspaceSettingsForm(request.POST or None, instance=workspace, prefix="workspace")

    if request.method == "POST" and user_form.is_valid() and profile_form.is_valid() and workspace_form.is_valid() :
        update_teacher_settings(user_form=user_form, profile_form=profile_form, workspace_form=workspace_form)
        messages.success(request, "Settings updated seccessfully")

        return redirect("accounts:profile")

    return render(request, "accounts/profile_edit.html", {
                                                            "user_form" : user_form,
                                                            "profile_form" : profile_form,
                                                            "workspace_form" : workspace_form
                                                        })