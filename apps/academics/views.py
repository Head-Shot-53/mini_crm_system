from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import Http404
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator


from apps.workspaces.selectors import get_user_workspace

from apps.students.models import Student
from .forms import SubjectForm, GroupCreateForm, GroupEditForm, GroupJoinForm
from .models import Subject, Group, GroupMembership
from .selectors import get_active_group_memberships, get_workspace_groups_with_counts, get_group_membership_history
from .services import create_group, update_group, join_student_to_group, leave_student_from_group, change_group_status


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
@require_POST
def subject_toggle_active_view(request, subject_id):
    workspace = get_current_workspace(request.user)

    with transaction.atomic():
        subject = get_object_or_404(
            Subject.objects.select_for_update(),
            id=subject_id,
            workspace=workspace
        )

        subject.is_active = not subject.is_active

        subject.save(
            update_fields=["is_active", "updated_at"])

    messages.success(request,
        "Subject status updated successfully."
    )

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

    history = (
        get_group_membership_history(
            workspace=workspace,
            group_id=group.id
        )
        .filter(
            left_at__isnull=False
        )
    )

    history_paginator = Paginator(history, 10)

    history_page = history_paginator.get_page(
        request.GET.get("history_page")
    )

    available_seats = None

    if group.max_students is not None:
        available_seats = max(
            0,
            group.max_students - group.active_members_count
        )

    can_join = (
        group.is_active and group.subject.is_active
        and available_seats is None or available_seats > 0)

    join_form = GroupJoinForm(
        workspace=workspace,
        group=group
    )

    return render(request, "academics/group_detail.html",
        {
            "group": group,
            "memberships": memberships,
            "history_page": history_page,
            "available_seats": available_seats,
            "can_join": can_join,
            "join_form": join_form
        }
    )


@login_required
def group_edit_view(request, group_id):
    workspace = get_current_workspace(request.user)

    group = get_object_or_404(Group,
        id=group_id,
        workspace=workspace,
        subject__workspace=workspace
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


@login_required
@require_POST
def group_join_view(request, group_id):
    workspace = get_current_workspace(request.user)

    group = get_object_or_404(
        Group,
        id=group_id,
        workspace=workspace,
        subject__workspace=workspace
    )

    form = GroupJoinForm(
        request.POST,
        workspace=workspace,
        group=group
    )

    if not form.is_valid():
        messages.error(request,
            "The selected student is not eligible "
            "to join this group."
        )

        return redirect(
            "academics:group_detail",
            group_id=group.id
        )

    try:
        join_student_to_group(
            workspace=workspace,
            group_id=group.id,
            student_id=form.cleaned_data["student"].id
        )

    except ValidationError as error:
        messages.error(request, error.messages[0])

    except IntegrityError:
        messages.error(request,
            "This student is already a member "
            "or the operation could not be completed."
        )

    except Student.DoesNotExist:
        messages.error(request,
            "The selected student is no longer available."
        )

    except Group.DoesNotExist:
        raise Http404("Group not found.")

    else:
        messages.success(request,
            "Student added to the group successfully."
        )

    return redirect(
        "academics:group_detail",
        group_id=group.id
    )


@login_required
@require_POST
def group_leave_view(request, group_id, student_id):
    workspace = get_current_workspace(
        request.user
    )

    group = get_object_or_404(
        Group,
        id=group_id,
        workspace=workspace,
        subject__workspace=workspace
    )

    try:
        leave_student_from_group(
            workspace=workspace,
            group_id=group.id,
            student_id=student_id
        )

    except Student.DoesNotExist:
        raise Http404("Student not found.")

    except Group.DoesNotExist:
        raise Http404("Group not found.")

    except GroupMembership.DoesNotExist:
        messages.error(request,
            "This student is not a current "
            "member of the group."
        )

    except ValidationError as error:
        messages.error(request, error.messages[0])

    else:
        messages.success(request,
            "Student removed from the group successfully."
        )

    return redirect(
        "academics:group_detail",
        group_id=group.id
    )


@login_required
@require_POST
def group_status_view(request, group_id, action):
    if action not in {"activate", "deactivate"}:
        raise Http404(
            "Unknown group status action."
        )

    workspace = get_current_workspace(
        request.user
    )

    group = get_object_or_404(
        Group,
        id=group_id,
        workspace=workspace,
        subject__workspace=workspace
    )

    try:
        change_group_status(
            workspace=workspace,
            group_id=group.id,
            action=action
        )

    except ValidationError as error:
        messages.error(
            request,
            error.messages[0]
        )

    except Group.DoesNotExist:
        raise Http404("Group not found.")

    else:
        messages.success(request,
            "Group status updated successfully."
        )

    return redirect(
        "academics:group_detail",
        group_id=group.id
    )