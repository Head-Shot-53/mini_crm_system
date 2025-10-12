from django.urls import path

from .views import *

app_name = "academics"

urlpatterns = [
    path("subjects/", subject_list_view, name="subject_list"),
    path("subjects/create/", subject_create_view, name="subject_create"),
    path("subject/<uuid:subject_id>/edit/", subject_edit_view, name="subject_edit"),
    path("subject/<uuid:subject_id>/toogle-active/", subject_toggle_active_view, name="subject_toggle_active"),

    path("groups/", group_list_view, name="group_list"),
    path("groups/create/", group_create_view, name="group_create"),
    path("groups/<uuid:group_id>/", group_detail_view, name="group_detail"),
    path("groups/<uuid:group_id>/edit/", group_edit_view, name="group_edit"),

    path("groups/<uuid:group_id>/join/", group_join_view, name="group_join"),
    path("groups/<uuid:group_id>/members/<uuid:student_id>/leave/", group_leave_view, name="group_leave"),
    path("groups/<uuid:group_id>/status/<str:action>/",group_status_view, name="group_status"),
    
]