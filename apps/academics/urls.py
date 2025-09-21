from django.urls import path

from .views import subject_create_view, subject_edit_view, subject_list_view, subject_toggle_active_view

app_name = "academics"

urlpatterns = [
    path("subjects/", subject_list_view, name="subject_list"),
    path("subjects/create/", subject_create_view, name="subject_create"),
    path("subject/<uuid:subject_id>/edit/", subject_edit_view, name="subject_edit"),
    path("subject/<uuid:subject_id>/toogle-active/", subject_toggle_active_view, name="subject_toggle_active"),
    
]