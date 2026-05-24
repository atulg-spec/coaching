from django.contrib import admin
from .models import Staff

@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ('employee_id', 'get_full_name', 'designation', 'subject_expertise', 'is_active')
    list_filter = ('designation', 'is_active')
    search_fields = ('employee_id', 'user__first_name', 'user__last_name', 'subject_expertise')

    def get_full_name(self, obj):
        return obj.user.get_full_name()
    get_full_name.short_description = 'Name'
