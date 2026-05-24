from django.urls import path
from . import views

urlpatterns = [
    path('collect/', views.collect_fee, name='collect_fee'),
    path('dues/', views.dues_report, name='dues_report'),
    path('history/', views.payment_history, name='payment_history'),
    path('receipt/<int:pk>/', views.receipt, name='receipt'),
    path('receipt/combined/', views.combined_receipt, name='combined_receipt'),
    path('staff-salary/', views.pay_staff_salary, name='pay_staff_salary'),
    path('staff-salary/history/', views.staff_salary_history, name='staff_salary_history'),
    path('inquiries/', views.inquiry_list, name='inquiry_list'),
]
