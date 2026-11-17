from django.contrib import admin
from .models import Notice

@admin.register(Notice)
class NoticeAdmin(admin.ModelAdmin):
    list_display = ('title', 'target_audience', 'date_posted', 'is_active')
    list_filter = ('target_audience', 'is_active', 'date_posted')
    search_fields = ('title', 'content')
