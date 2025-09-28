from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

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

    students = (Student.objects.filter(workspace=workspace).order_by("last_name","first_name","id"))

    return render(request,"students/student_list.html",{"students": students})

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