from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from payments.models import Inquiry
from students.models import Student
from batches.models import Batch
from attendance.models import AttendanceSession
from payments.models import Payment
from staff.models import Staff
from accounts.decorators import admin_required, staff_or_admin_required


@staff_or_admin_required
def dashboard_home(request):
    today = timezone.now().date()
    user = request.user

    if user.role == 'admin':
        context = {
            'is_admin': True,
            'total_students':  Student.objects.filter(is_active=True).count(),
            'total_batches':   Batch.objects.filter(is_active=True).count(),
            'today_sessions':  AttendanceSession.objects.filter(date=today).count(),
            'pending_dues':    Payment.objects.filter(status='pending').count(),
            'new_inquiries':   Inquiry.objects.filter(is_followed_up=False).count(),
            'todays_batches':  Batch.objects.filter(is_active=True)[:5],
            'recent_payments': Payment.objects.select_related('student__user', 'batch').order_by('-payment_date')[:5],
            'today': today,
        }
    else:
        # Staff: only their batches
        try:
            staff_profile = user.staff
            my_batches = Batch.objects.filter(teacher=staff_profile, is_active=True)
        except Staff.DoesNotExist:
            my_batches = Batch.objects.none()

        context = {
            'is_admin': False,
            'my_batches': my_batches,
            'today_sessions': AttendanceSession.objects.filter(
                date=today, batch__in=my_batches
            ).count(),
            'today': today,
        }

    return render(request, 'dashboard/home.html', context)


def home(request):
    return render(request, 'public/index.html')

def about(request):
    return render(request, 'public/about.html')

def courses(request):
    batches = Batch.objects.filter(is_active=True)
    return render(request, 'public/courses.html', {'batches': batches})

def contact(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        email = request.POST.get('email', '')
        interested_class = request.POST.get('interested_class', '')
        message = request.POST.get('message', '')
        Inquiry.objects.create(
            name=name, phone=phone, email=email,
            interested_class=interested_class, message=message
        )
        messages.success(request, 'Your inquiry has been submitted. We will contact you soon!')
        return redirect('contact')
    return render(request, 'public/contact.html')
