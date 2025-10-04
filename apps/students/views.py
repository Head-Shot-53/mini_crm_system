from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.http import HttpResponseForbidden
from django.core.paginator import Paginator
from django.db.models import Count, Q

from .services.lifecycle import STATUS_TRANSITIONS, change_student_status

from apps.academics.models import Subject
from apps.academics.services import assign_subject_to_student, update_student_enrollment
from apps.workspaces.selectors import get_user_workspace

from .forms import StudentForm, SubjectAssignmentForm, StudentFilterForm, EnrollmentUpdateForm
from .selectors import get_filtered_students

from .models import Student
from apps.academics.models import StudentSubject


def get_current_workspace(user):
    workspace = get_user_workspace(user)

    if workspace is None:
        raise Http404("Workspace not found")

    return workspace

@login_required
def student_list_view(request):
    workspace = get_current_workspace(request.user)

    show_archived = (request.GET.get("view") == "archived")

    filter_form = StudentFilterForm(
        request.GET,
        workspace=workspace,
        archived=show_archived
    )

    if filter_form.is_valid():
        filters = filter_form.cleaned_data

        students = get_filtered_students(
            workspace=workspace,
            archived=show_archived,
            q=filters.get("q", ""),
            status=filters.get("status"),
            subject=filters.get("subject")
        )

    else:
        students = Student.objects.none()

    paginator = Paginator(students, per_page=10)

    page_number = request.GET.get("page")

    page_obj = paginator.get_page(page_number)

    query_params = request.GET.copy()

    query_params.pop("page", None)

    if show_archived:
        query_params.pop("status", None)

    page_query = query_params.urlencode()

    return render(request, "students/student_list.html",
        {
            "students": page_obj,
            "page_obj": page_obj,
            "filter_form": filter_form,
            "show_archived": show_archived,
            "page_query": page_query,
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

    enrollment_stats = (
        student.subject_enrollments
        .filter(
            subject__workspace=workspace,
        )
        .aggregate(
            total=Count("id"),

            active=Count(
                "id",
                filter=Q(
                    status=StudentSubject.Status.ACTIVE
                ),
            ),

            paused=Count(
                "id",
                filter=Q(
                    status=StudentSubject.Status.PAUSED
                ),
            ),

            completed=Count(
                "id",
                filter=Q(
                    status=StudentSubject.Status.COMPLETED
                ),
            ),
        )
    )

    has_available_subjects = (assignment_form.fields["subject"].queryset.exists())

    return render(request,"students/student_detail.html",
        {
            "student": student,
            "enrollments": enrollments,
            "assignment_form": assignment_form,
            "has_available_subjects": has_available_subjects,
            "enrollment_stats": enrollment_stats,
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


@login_required
def enrollment_edit_view(request, student_id, enrollment_id):
    workspace = get_current_workspace(
        request.user
    )

    student = get_object_or_404(
        Student,
        id=student_id,
        workspace=workspace
    )

    if student.status == Student.Status.ARCHIVED:
        return HttpResponseForbidden(
            "Archived students cannot have their enrollments edited."
        )

    enrollment = get_object_or_404(
        StudentSubject.objects.select_related(
            "subject"
        ),
        id=enrollment_id,
        student=student,
        subject__workspace=workspace
    )

    form = EnrollmentUpdateForm(
        request.POST or None,
        instance=enrollment
    )

    if request.method == "POST" and form.is_valid():
        try:
            update_student_enrollment(
                workspace=workspace,
                student_id=student.id,
                enrollment_id=enrollment.id,
                level=form.cleaned_data["level"],
                status=form.cleaned_data["status"],
                started_on=form.cleaned_data["started_on"],
                notes=form.cleaned_data["notes"],
            )

        except ValidationError:
            form.add_error(
                None,
                "Cannot update this enrollment. "
                "Check its current status and submitted values.",
            )

        except (
            Student.DoesNotExist,
            StudentSubject.DoesNotExist,
        ):
            raise Http404(
                "Student enrollment not found."
            )

        else:
            messages.success(
                request,
                "Student enrollment updated successfully.",
            )

            return redirect(
                "students:student_detail",
                student_id=student.id,
            )

    return render(request, "students/enrollment_form.html",
        {
            "student": student,
            "enrollment": enrollment,
            "form": form,
        }
    )