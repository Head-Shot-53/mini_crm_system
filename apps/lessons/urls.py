from django.urls import path

from . import views


app_name = "lessons"


urlpatterns = [
    path("", views.calendar_view, name="calendar"),
    
    path("create/individual/", views.individual_lesson_create_view, name="create_individual"),
    path("create/group/", views.group_lesson_create_view, name="create_group"),

    path("<uuid:lesson_id>/", views.lesson_detail_view, name="lesson_detail"),
    path("<uuid:lesson_id>/reschedule/", views.lesson_reschedule_view, name="reschedule"),
    path("<uuid:lesson_id>/status/<str:action>/", views.lesson_status_view, name="lesson_status"),
    
    path("<uuid:lesson_id>/attendance/", views.lesson_attendance_view, name="attendance"),
    path("<uuid:lesson_id>/attendance/<uuid:attendance_id>/mark/", views.attendance_mark_view, name="attendance_mark"),
]