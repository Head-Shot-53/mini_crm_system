from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from apps.workspaces.selectors import get_user_workspace

from .forms import SubjectForm
from .models import Subject

@login_required
def subject_list_view(request):
    workspace = get_user_workspace(request.user)

    subjects = Subject.objects.filter(workspace=workspace).order_by("name")

    return render(request, "academics/subject_list.html", {"subjects":subjects})

@login_required
def subject_create_view(request):
    workspace = get_user_workspace(request.user)

    if workspace is None:
        messages.error(request, "Your account does not have a workspace.")

        return redirect("accounts:profile")

    form = SubjectForm(request.POST or None, workspace=workspace)

    if request.method == "POST" and form.is_valid():
        subject = form.save(commit=False)
        subject.workspace = workspace
        subject.save()

        messages.success(request, "Subject created successfully.")

        return redirect("academics:subject_list")

    return render(request, "academics/subject_form.html", {"form":form, "page_title" : "Created Subject"})

@login_required
def subject_edit_view(request, subject_id):
    workspace = get_user_workspace(request.user)

    subject = get_object_or_404(Subject, id=subject_id, workspace=workspace)

    form = SubjectForm(request.POST or None, instance=subject, workspace=workspace)

    if request.method == "POST" and form.is_valid():
        form.save()

        messages.success(request, "Subject updated seccessfully.")

        return redirect("academics:subject_list")

    return render(request, "academics/subject_form.html", {"form":form, "page_title" : "Edit Subject"})

@login_required
def subject_toggle_active_view(request, subject_id):
    if request.method != "POST":
        return redirect("academics:subject_list")

    workspace = get_user_workspace(request.user)

    subject = get_object_or_404(Subject, id=subject_id, workspace=workspace)

    subject.is_active = not subject.is_active

    subject.save(update_fields=("is_active", "updated_at"))
    messages.success(request, "Subject status updated successfully.")

    return redirect("academics:subject_list")