from django.contrib import admin
from .models import Student

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('student_id', 'get_full_name', 'current_class', 'board', 'is_active')
    list_filter = ('current_class', 'board', 'is_active')
    search_fields = ('student_id', 'user__first_name', 'user__last_name', 'parent_phone')

    def get_full_name(self, obj):
        return obj.user.get_full_name()
    get_full_name.short_description = 'Name'
