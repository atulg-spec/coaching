"""
URL configuration for success_coaching project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('grappelli/', include('grappelli.urls')),
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('accounts/', include('accounts.urls')),
    path('dashboard/students/', include('students.urls')),
    path('dashboard/staff/', include('staff.urls')),
    path('dashboard/batches/', include('batches.urls')),
    path('dashboard/attendance/', include('attendance.urls')),
    path('dashboard/payments/', include('payments.urls')),
    path('student-portal/', include('student_portal.urls')),
    path('chatbot/', include('chatbot.urls')),
]

from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
