from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.http import Http404


from apps.workspaces.selectors import get_user_workspace

from .forms import SubjectForm, GroupCreateForm, GroupEditForm
from .models import Subject, Group
from .selectors import get_active_group_memberships, get_workspace_groups_with_counts
from .services import create_group, update_group


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


def get_current_workspace(user):
    workspace = get_user_workspace(user)

    if workspace is None:
        raise Http404(
            "Workspace not found."
        )

    return workspace


@login_required
def group_list_view(request):
    workspace = get_current_workspace(request.user)

    groups = get_workspace_groups_with_counts(workspace=workspace)

    return render(request, "academics/group_list.html", {"groups": groups})


@login_required
def group_create_view(request):
    workspace = get_current_workspace(
        request.user
    )

    form = GroupCreateForm(request.POST or None,
        workspace=workspace
    )

    if request.method == "POST" and form.is_valid():
        try:
            group = create_group(
                workspace=workspace,
                subject_id=form.cleaned_data["subject"].id,
                name=form.cleaned_data["name"],
                description=form.cleaned_data["description"],
                max_students=form.cleaned_data["max_students"]
            )

        except ValidationError as error:
            for message in error.messages:
                form.add_error(None, message)

        except IntegrityError:
            form.add_error(
                None,
                "Could not create the group. "
                "Its name may already be in use."
            )

        except Group.subject.RelatedObjectDoesNotExist:
            form.add_error(
                "subject",
                "The selected subject is no longer available."
            )

        else:
            messages.success(request, "Group created successfully.")

            return redirect("academics:group_detail", group_id=group.id)

    return render(request, "academics/group_form.html",
        {
            "form": form,
            "page_title": "Create Group"
        }
    )


@login_required
def group_detail_view(request, group_id):
    workspace = get_current_workspace(
        request.user
    )

    group = get_object_or_404(
        get_workspace_groups_with_counts(
            workspace=workspace
        ),
        id=group_id
    )

    memberships = get_active_group_memberships(
        workspace=workspace,
        group_id=group.id
    )

    available_seats = None

    if group.max_students is not None:
        available_seats = max(0, group.max_students - group.active_members_count)

    return render(request, "academics/group_detail.html",
        {
            "group": group,
            "memberships": memberships,
            "available_seats": available_seats
        }
    )


@login_required
def group_edit_view(request, group_id):
    workspace = get_current_workspace(request.user)

    group = get_object_or_404(Group,
        id=group_id,
        workspace=workspace
    )

    form = GroupEditForm(
        request.POST or None,
        instance=group
    )

    if request.method == "POST" and form.is_valid():
        try:
            updated_group = update_group(
                workspace=workspace,
                group_id=group.id,
                name=form.cleaned_data["name"],
                description=form.cleaned_data["description"],
                max_students=form.cleaned_data["max_students"]
            )

        except ValidationError as error:
            for message in error.messages:
                form.add_error(None, message)

        except IntegrityError:
            form.add_error(
                None,
                "Could not save the group. "
                "Its name may already be in use."
            )

        except Group.DoesNotExist:
            raise Http404(
                "Group not found."
            )

        else:
            messages.success(request, "Group updated successfully.")

            return redirect("academics:group_detail", group_id=updated_group.id)

    return render(request, "academics/group_form.html",
        {
            "form": form,
            "page_title": "Edit Group"
        }
    )