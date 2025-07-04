from django.contrib import admin
from .models import Note

@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ('title', 'client', 'created_at')
    list_filter = ('created_at', 'client')
    search_fields = ('title', 'description')