from django.urls import path
from . import views

urlpatterns = [
    # Full Chat views
    path('', views.dashboard_chat_view, name='chatbot_dashboard'),
    path('student/', views.student_chat_view, name='chatbot_student'),
    
    # Admin Credentials & Model Configuration
    path('settings/', views.admin_settings_view, name='chatbot_settings'),

    # JSON API Endpoints
    path('api/send/', views.api_send_message, name='chatbot_api_send'),
    path('api/test-connection/', views.api_test_connection, name='chatbot_api_test_connection'),
    path('api/conversations/', views.api_get_conversations, name='chatbot_api_conversations'),
    path('api/conversations/new/', views.api_new_conversation, name='chatbot_api_new_conversation'),
    path('api/conversations/<int:conversation_id>/messages/', views.api_get_messages, name='chatbot_api_messages'),
    path('api/conversations/<int:conversation_id>/delete/', views.api_delete_conversation, name='chatbot_api_delete_conversation'),
]
