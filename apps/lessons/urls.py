from django.urls import path

from . import views


app_name = "lessons"


urlpatterns = [
    path("", views.calendar_view, name="calendar"),
    path("create/individual/", views.individual_lesson_create_view, name="create_individual"),
    path("create/group/", views.group_lesson_create_view, name="create_group"),
    path("<uuid:lesson_id>/", views.lesson_detail_view, name="lesson_detail"),
    path("<uuid:lesson_id>/reschedule/", views.lesson_reschedule_view, name="reschedule"),
]