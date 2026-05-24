from django.urls import path
from . import views

urlpatterns = [
    path('', views.student_home, name='student_portal_home'),
    path('attendance/', views.student_attendance, name='student_portal_attendance'),
    path('fees/', views.student_fees, name='student_portal_fees'),
    path('timetable/', views.student_timetable, name='student_portal_timetable'),
    path('profile/', views.student_profile, name='student_portal_profile'),
]
