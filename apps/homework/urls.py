from django.urls import path

from apps.homework import views


app_name = "homework"


urlpatterns = [
    path("", views.assignment_list_view,name="assignment-list"),

    path("new/individual/", views.assignment_individual_create_view, name="assignment-individual-create"),
    
    path("new/group/", views.assignment_group_create_view, name="assignment-group-create"),

    path("<uuid:assignment_id>/", views.assignment_detail_view, name="assignment-detail"),
    path("<uuid:assignment_id>/edit/", views.assignment_edit_view, name="assignment-edit"),
    path("<uuid:assignment_id>/publish/", views.assignment_publish_view, name="assignment-publish"),
    
    path("submissions/<uuid:submission_id>/", views.submission_detail_view, name="submission-detail"),
]