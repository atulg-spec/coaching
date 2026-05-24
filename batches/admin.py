from django.contrib import admin
from .models import Subject, Batch

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'code')

@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ('batch_name', 'batch_code', 'class_level', 'board', 'teacher', 'is_active')
    list_filter = ('class_level', 'board', 'is_active')
    search_fields = ('batch_name', 'batch_code')
    filter_horizontal = ('students', 'subjects')
