from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.homework.forms import GroupAssignmentDraftForm, IndividualAssignmentDraftForm

from apps.homework.models import Assignment, AssignmentSubmission

from apps.homework.selectors import get_assignment, get_assignment_submission_overview, get_workspace_assignments
from apps.homework.services.assignments import create_assignment_draft, update_assignment_draft
from apps.homework.services.publication import publish_assignment

from apps.workspaces.selectors import get_user_workspace


def _get_workspace(user):
    workspace = get_user_workspace(user)

    if workspace is None:
        raise Http404("Workspace not found.")

    return workspace


def _datetime_local_value(value):
    if value is None:
        return ""

    value = timezone.localtime(value)

    return value.strftime("%Y-%m-%dT%H:%M")


def _assignment_initial_data(assignment):
    data = {
        "subject": assignment.subject_id,
        "lesson": assignment.lesson_id,
        "title": assignment.title,
        "description": assignment.description,
        "due_at": _datetime_local_value(
            assignment.due_at
        )
    }

    if assignment.student_id:
        data["student"] = assignment.student_id

    if assignment.group_id:
        data["group"] = assignment.group_id

    return data


def _add_validation_error(form, exc):
    if hasattr(exc, "message_dict"):
        for field, errors in exc.message_dict.items():
            target_field = (
                field
                if field in form.fields
                else None
            )

            for error in errors:
                form.add_error(target_field, error)

        return

    for message in exc.messages:
        form.add_error(None, message)


def _get_recipient_state(recipient):
    try:
        submission = recipient.submission
    except AssignmentSubmission.DoesNotExist:
        return {
            "label": "Not Submitted",
            "submission": None
        }

    if submission.status == AssignmentSubmission.Status.REVIEWED:
        label = "Reviewed"

    elif submission.is_late:
        label = "Late"

    else:
        label = "Submitted"

    return {
        "label": label,
        "submission": submission
    }


@login_required
def assignment_list_view(request):
    workspace = _get_workspace(request.user)

    assignments = get_workspace_assignments(workspace=workspace)

    context = {
        "workspace": workspace,
        "assignments": assignments
    }

    return render(request, "homework/assignment_list.html",context)


@login_required
def assignment_individual_create_view(request):
    workspace = _get_workspace(request.user)

    if request.method == "POST":
        form = IndividualAssignmentDraftForm(
            request.POST,
            workspace=workspace
        )

        if form.is_valid():
            try:
                assignment = create_assignment_draft(
                    workspace=workspace,
                    subject_id=(
                        form.cleaned_data["subject"].id
                    ),
                    student_id=(
                        form.cleaned_data["student"].id
                    ),
                    group_id=None,
                    lesson_id=(
                        form.cleaned_data["lesson"].id
                        if form.cleaned_data["lesson"]
                        else None
                    ),
                    title=form.cleaned_data["title"],
                    description=(
                        form.cleaned_data["description"]
                    ),
                    due_at=form.cleaned_data["due_at"]
                )

            except ValidationError as exc:
                _add_validation_error(form, exc)

            else:
                messages.success(request,
                    "Individual assignment draft created."
                )

                return redirect(
                    "homework:assignment-detail",
                    assignment_id=assignment.id
                )

    else:
        form = IndividualAssignmentDraftForm(workspace=workspace)

    return render(request, "homework/assignment_form.html",
        {
            "form": form,
            "page_title": (
                "Create individual assignment"
            ),
            "submit_label": "Create draft"
        }
    )


@login_required
def assignment_group_create_view(request):
    workspace = _get_workspace(request.user)

    if request.method == "POST":
        form = GroupAssignmentDraftForm(request.POST, workspace=workspace)

        if form.is_valid():
            try:
                assignment = create_assignment_draft(
                    workspace=workspace,
                    subject_id=(
                        form.cleaned_data["subject"].id
                    ),
                    student_id=None,
                    group_id=(
                        form.cleaned_data["group"].id
                    ),
                    lesson_id=(
                        form.cleaned_data["lesson"].id
                        if form.cleaned_data["lesson"]
                        else None
                    ),
                    title=form.cleaned_data["title"],
                    description=(
                        form.cleaned_data["description"]
                    ),
                    due_at=form.cleaned_data["due_at"]
                )

            except ValidationError as exc:
                _add_validation_error(form, exc)

            else:
                messages.success(request,
                    "Group assignment draft created."
                )

                return redirect(
                    "homework:assignment-detail",
                    assignment_id=assignment.id
                )

    else:
        form = GroupAssignmentDraftForm(workspace=workspace)

    return render(request, "homework/assignment_form.html",
        {
            "form": form,
            "page_title": (
                "Create group assignment"
            ),
            "submit_label": "Create draft"
        }
    )


@login_required
def assignment_detail_view(request, assignment_id):
    workspace = _get_workspace(request.user)

    try:
        assignment = get_assignment(
            workspace=workspace,
            assignment_id=assignment_id
        )
    except Assignment.DoesNotExist:
        raise Http404(
            "Assignment not found."
        )

    recipients = (
        get_assignment_submission_overview(
            workspace=workspace,
            assignment=assignment
        )
    )

    recipient_rows = []

    for recipient in recipients:
        state = _get_recipient_state(recipient)

        recipient_rows.append(
            {
                "recipient": recipient,
                "state": state["label"],
                "submission": (
                    state["submission"]
                )
            }
        )

    context = {
        "assignment": assignment,
        "recipient_rows": recipient_rows
    }

    return render(request, "homework/assignment_detail.html",context)


@login_required
def assignment_edit_view(request, assignment_id):
    workspace = _get_workspace(request.user)

    try:
        assignment = get_assignment(
            workspace=workspace,
            assignment_id=assignment_id
        )
    except Assignment.DoesNotExist:
        raise Http404(
            "Assignment not found."
        )

    if assignment.status != Assignment.Status.DRAFT:
        messages.error(
            request,
            "Only draft assignments can be edited."
        )

        return redirect(
            "homework:assignment-detail",
            assignment_id=assignment.id
        )

    is_individual = assignment.student_id is not None

    FormClass = (
        IndividualAssignmentDraftForm
        if is_individual
        else GroupAssignmentDraftForm
    )

    if request.method == "POST":
        form = FormClass(
            request.POST,
            workspace=workspace
        )

        if form.is_valid():
            try:
                update_assignment_draft(
                    workspace=workspace,
                    assignment_id=assignment.id,
                    subject_id=(
                        form.cleaned_data["subject"].id
                    ),
                    student_id=(
                        form.cleaned_data["student"].id
                        if is_individual
                        else None
                    ),
                    group_id=(
                        form.cleaned_data["group"].id
                        if not is_individual
                        else None
                    ),
                    lesson_id=(
                        form.cleaned_data["lesson"].id
                        if form.cleaned_data["lesson"]
                        else None
                    ),
                    title=form.cleaned_data["title"],
                    description=(
                        form.cleaned_data["description"]
                    ),
                    due_at=form.cleaned_data["due_at"]
                )

            except ValidationError as exc:
                _add_validation_error(form,exc)

            else:
                messages.success(
                    request,
                    "Assignment draft updated."
                )

                return redirect(
                    "homework:assignment-detail",
                    assignment_id=assignment.id
                )

    else:
        form = FormClass(
            workspace=workspace,
            initial=_assignment_initial_data(
                assignment
            )
        )

    return render(
        request,
        "homework/assignment_form.html",
        {
            "form": form,
            "assignment": assignment,
            "page_title": "Edit assignment",
            "submit_label": "Save changes"
        }
    )


@login_required
@require_POST
def assignment_publish_view(request, assignment_id):
    workspace = _get_workspace(request.user)

    try:
        publish_assignment(
            workspace=workspace,
            assignment_id=assignment_id
        )

    except Assignment.DoesNotExist:
        raise Http404(
            "Assignment not found."
        )

    except ValidationError as exc:
        messages.error(
            request,
            " ".join(exc.messages)
        )

    else:
        messages.success(
            request,
            "Assignment published successfully."
        )

    return redirect(
        "homework:assignment-detail",
        assignment_id=assignment_id
    )