from django.urls import path
from . import views

urlpatterns = [
    path('', views.batch_list, name='batch_list'),
    path('add/', views.batch_add, name='batch_add'),
    path('<int:pk>/', views.batch_detail, name='batch_detail'),
    path('<int:pk>/edit/', views.batch_edit, name='batch_edit'),
    path('<int:batch_id>/add-student/', views.batch_add_student, name='batch_add_student'),
    path('<int:batch_id>/remove-student/<int:student_id>/', views.batch_remove_student, name='batch_remove_student'),
    
    path('<int:batch_id>/upload-material/', views.upload_material, name='upload_material'),
    path('delete-material/<int:material_id>/', views.delete_material, name='delete_material'),
    
    path('subjects/', views.subject_list, name='subject_list'),
    path('subjects/add/', views.subject_add, name='subject_add'),
    path('subjects/<int:pk>/edit/', views.subject_edit, name='subject_edit'),
]
