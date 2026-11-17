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

from .models import StudyMaterial

@admin.register(StudyMaterial)
class StudyMaterialAdmin(admin.ModelAdmin):
    list_display = ('title', 'batch', 'uploaded_by', 'uploaded_at')
    list_filter = ('batch', 'uploaded_at')
    search_fields = ('title', 'description', 'batch__batch_name')
