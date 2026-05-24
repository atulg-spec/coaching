from django.urls import path
from . import views

urlpatterns = [
    path('mark/<int:batch_id>/', views.mark_attendance, name='mark_attendance'),
    path('reports/', views.attendance_reports, name='attendance_reports'),
    path('student/<int:student_id>/', views.student_attendance, name='student_attendance'),
    path('staff/mark/', views.mark_staff_attendance, name='mark_staff_attendance'),
    path('staff/reports/', views.staff_attendance_reports, name='staff_attendance_reports'),
]
