from django.urls import path

from .views import *

app_name = "students"

urlpatterns = [
    path("",student_list_view,name="student_list"),
    path("create/",student_create_view,name="student_create"),
    path("<uuid:student_id>/",student_detail_view,name="student_detail"),
    path("<uuid:student_id>/edit/",student_edit_view,name="student_edit"),
    path("<uuid:student_id>/status/<str:action>/", student_status_view, name="student_status"),
    path("<uuid:student_id>/subjects/<uuid:enrollment_id>/edit/", enrollment_edit_view, name="enrollment_edit"),
]