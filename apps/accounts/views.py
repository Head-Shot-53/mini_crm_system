from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

from .forms import TeacherRegistrationForm
from .services import register_teacher

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

