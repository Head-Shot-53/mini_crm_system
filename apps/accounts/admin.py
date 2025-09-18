from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import TeacherProfile, User

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("email" , )

    list_display = ('email', 'first_name', 'last_name', 'is_staff', 'is_active')
    search_fields = ('email', 'first_name', 'last_name')
    fieldsets = (
        (
            None,
            {
                'fields' : ('email', 'password')
            }
        ),
        (
            "Personal info",
            {
                'fields' : ('first_name', 'last_name')
            }
        ),
        (
            "Permissions",
            {
                "fields" : ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")
            }
        ),
        (
            "important dates",
            {
                "fields" : ('last_login', 'date_joined')
            }
        ),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes" : ("wide", ),
                "fields" : ('email', 'password1', 'password2', 'is_staff', 'is_active'),
            },
        ),
    )

@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'timezone', 'language', 'currency', 'default_lesson_duration', 'default_lesson_price')

    search_fields = ('user__email', 'user_first_name', "user__last_name")
