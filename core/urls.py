from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('courses/', views.courses, name='courses'),
    path('contact/', views.contact, name='contact'),
    path('book-demo/', views.book_demo, name='book_demo'),
    path('dashboard/', views.dashboard_home, name='dashboard_home'),
    path('dashboard/notices/', views.notice_list, name='notice_list'),
    path('dashboard/notices/add/', views.notice_create, name='notice_add'),
    path('dashboard/notices/<int:pk>/edit/', views.notice_update, name='notice_edit'),
    path('dashboard/notices/<int:pk>/delete/', views.notice_delete, name='notice_delete'),
]
