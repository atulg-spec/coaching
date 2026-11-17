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
from .models import Notice
from .forms import NoticeForm

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

@staff_or_admin_required
def notice_list(request):
    if request.user.role == 'admin':
        notices = Notice.objects.all()
    else:
        notices = Notice.objects.filter(target_audience__in=['all', 'staff'])
    return render(request, 'dashboard/notices/notice_list.html', {
        'notices': notices,
        'is_admin': request.user.role == 'admin'
    })

@admin_required
def notice_create(request):
    if request.method == 'POST':
        form = NoticeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Notice created successfully.')
            return redirect('notice_list')
    else:
        form = NoticeForm()
    return render(request, 'dashboard/notices/notice_form.html', {'form': form, 'title': 'Create Notice'})

@admin_required
def notice_update(request, pk):
    notice = get_object_or_404(Notice, pk=pk)
    if request.method == 'POST':
        form = NoticeForm(request.POST, instance=notice)
        if form.is_valid():
            form.save()
            messages.success(request, 'Notice updated successfully.')
            return redirect('notice_list')
    else:
        form = NoticeForm(instance=notice)
    return render(request, 'dashboard/notices/notice_form.html', {'form': form, 'title': 'Edit Notice'})

@admin_required
def notice_delete(request, pk):
    notice = get_object_or_404(Notice, pk=pk)
    if request.method == 'POST':
        notice.delete()
        messages.success(request, 'Notice deleted successfully.')
        return redirect('notice_list')
    return render(request, 'dashboard/notices/notice_confirm_delete.html', {'notice': notice})
def book_demo(request):
    if request.method == 'POST':
        import json
        from django.http import JsonResponse
        try:
            data = json.loads(request.body)
            name = data.get('name')
            phone = data.get('phone')
            cls = data.get('cls')
            stream = data.get('stream', '')
            city = data.get('city', '')
            mode = data.get('mode', '')
            message = f'City: {city}\nMode: {mode}\nStream: {stream}'
            from payments.models import Inquiry
            Inquiry.objects.create(
                name=name, phone=phone, email='',
                interested_class=cls, message=message
            )
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error'}, status=405)
