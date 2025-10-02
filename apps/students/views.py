from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.http import HttpResponseForbidden

from .services.lifecycle import STATUS_TRANSITIONS, change_student_status

from apps.academics.models import Subject
from apps.academics.services import assign_subject_to_student
from apps.workspaces.selectors import get_user_workspace

from .forms import StudentForm, SubjectAssignmentForm

from .models import Student


def get_current_workspace(user):
    workspace = get_user_workspace(user)

    if workspace is None:
        raise Http404("Workspace not found")

    return workspace

@login_required
def student_list_view(request):
    workspace = get_current_workspace(request.user)

    show_archived = (request.GET.get("view") == "archived")

    students = Student.objects.filter(workspace=workspace)

    if show_archived:
        students = students.filter(status=Student.Status.ARCHIVED)

    else:
        students = students.exclude(status=Student.Status.ARCHIVED)

    students = students.order_by("last_name", "first_name", "id")

    return render(request, "students/student_list.html",
        {
            "students": students,
            "show_archived": show_archived,
        }
    )

@login_required
def student_create_view(request):

    workspace = get_current_workspace(request.user)

    form = StudentForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        student = form.save(commit=False)

        student.workspace = workspace

        student.full_clean()

        student.save()

        messages.success(request,"Student created successfully.")

        return redirect("students:student_detail",student_id=student.id)

    return render(request,"students/student_form.html",{"form": form, "page_title": "Create Student"})

@login_required
def student_edit_view(request, student_id):
    workspace = get_current_workspace(request.user)

    student = get_object_or_404(Student, id=student_id, workspace=workspace)

    if student.status == Student.Status.ARCHIVED:
        messages.error(
            request,
            "Archived students cannot be edited."
        )

        return redirect(
            "students:student_detail",
            student_id=student.id
        )

    form = StudentForm(request.POST or None, instance=student)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request,"Student updated successfully.")

        return redirect("students:student_detail",student_id=student.id)

    return render(request,"students/student_form.html",{"form": form, "page_title": "Edit Student"})

@login_required
def student_detail_view(request,student_id):
    workspace = get_current_workspace(request.user)

    student = get_object_or_404(Student,id=student_id,workspace=workspace)

    if request.method == "POST" and student.status == Student.Status.ARCHIVED:
        return HttpResponseForbidden(
            "Archived students cannot receive new subjects."
        )

    assignment_form = SubjectAssignmentForm(
        request.POST if request.method == "POST" else None,
        workspace=workspace,
        student=student,
    )

    if request.method == "POST" and assignment_form.is_valid():
        try:
            assign_subject_to_student(
                workspace=workspace,
                student_id=student.id,
                subject_id=assignment_form.cleaned_data["subject"].id,
                level=assignment_form.cleaned_data["level"],
                started_on=assignment_form.cleaned_data["started_on"],
            )

        except ValidationError:
            assignment_form.add_error(
                None,
                "Cannot assign this subject. "
                "Check the student's status or existing enrollments.",
            )

        except Subject.DoesNotExist:
            assignment_form.add_error("subject","This subject is no longer available.")

        except IntegrityError:
            assignment_form.add_error("subject","This subject has already been assigned.")

        else:
            messages.success(request,"Subject assigned successfully.")

            return redirect("students:student_detail",student_id=student.id)

    enrollments = (student.subject_enrollments.filter(subject__workspace=workspace,).select_related("subject",).order_by("subject__name"))

    has_available_subjects = (assignment_form.fields["subject"].queryset.exists())

    return render(request,"students/student_detail.html",
        {
            "student": student,
            "enrollments": enrollments,
            "assignment_form": assignment_form,
            "has_available_subjects": has_available_subjects,
        }
    )

@login_required
@require_POST
def student_status_view(request, student_id, action):
    valid_actions = set(STATUS_TRANSITIONS) | {"restore"}

    if action not in valid_actions:
        raise Http404(
            "Unknown student status action."
        )

    workspace = get_current_workspace(request.user)

    try:
        student = change_student_status(
            workspace=workspace,
            student_id=student_id,
            action=action,
        )

    except Student.DoesNotExist:
        raise Http404(
            "Student not found."
        )

    except ValidationError as error:
        messages.error(request,error.messages[0])

        return redirect(
            "students:student_detail",
            student_id=student_id,
        )

    messages.success(request,"Student status updated successfully.")

    return redirect("students:student_detail",student_id=student.id)