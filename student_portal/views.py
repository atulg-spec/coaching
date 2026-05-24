from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.contrib import messages
from payments.models import Payment
from attendance.models import AttendanceRecord, AttendanceSession
from accounts.decorators import student_required
import datetime


@student_required
def student_home(request):
    try:
        student = request.user.student
    except Exception:
        return render(request, 'student_portal/no_profile.html', {})
    my_batches = student.batches.filter(is_active=True)
    today = timezone.now().date()

    # Attendance % this month per batch
    batch_stats = []
    for batch in my_batches:
        this_month = today.replace(day=1)
        total = AttendanceSession.objects.filter(batch=batch, date__gte=this_month).count()
        present = AttendanceRecord.objects.filter(
            student=student, session__batch=batch,
            session__date__gte=this_month, status='present'
        ).count()
        pct = round((present / total * 100), 1) if total > 0 else 0
        batch_stats.append({'batch': batch, 'total': total, 'present': present, 'percentage': pct})

    # Fee summary
    pending_fees = Payment.objects.filter(student=student, status='pending').count()
    paid_fees = Payment.objects.filter(student=student, status='paid').count()

    return render(request, 'student_portal/home.html', {
        'student': student,
        'my_batches': my_batches,
        'batch_stats': batch_stats,
        'pending_fees': pending_fees,
        'paid_fees': paid_fees,
        'today': today,
    })


@student_required
def student_attendance(request):
    try:
        student = request.user.student
    except Exception:
        return render(request, 'student_portal/no_profile.html', {})
    my_batches = student.batches.filter(is_active=True)
    selected_batch_id = request.GET.get('batch')
    selected_batch = None
    records = []
    batch_stats = []

    for batch in my_batches:
        total = AttendanceRecord.objects.filter(student=student, session__batch=batch).count()
        present = AttendanceRecord.objects.filter(student=student, session__batch=batch, status='present').count()
        pct = round((present / total * 100), 1) if total > 0 else 0
        batch_stats.append({'batch': batch, 'total': total, 'present': present, 'percentage': pct})

    if selected_batch_id:
        selected_batch = get_object_or_404(my_batches, pk=selected_batch_id)
        records = AttendanceRecord.objects.filter(
            student=student, session__batch=selected_batch
        ).select_related('session').order_by('-session__date')

    return render(request, 'student_portal/attendance.html', {
        'student': student,
        'my_batches': my_batches,
        'batch_stats': batch_stats,
        'selected_batch': selected_batch,
        'records': records,
    })


@student_required
def student_fees(request):
    try:
        student = request.user.student
    except Exception:
        return render(request, 'student_portal/no_profile.html', {})
    payments = Payment.objects.filter(student=student).select_related('batch').order_by('-month')
    return render(request, 'student_portal/fees.html', {
        'student': student,
        'payments': payments,
    })


@student_required
def student_timetable(request):
    try:
        student = request.user.student
    except Exception:
        return render(request, 'student_portal/no_profile.html', {})
    my_batches = student.batches.filter(is_active=True).select_related('teacher__user').prefetch_related('subjects')
    return render(request, 'student_portal/timetable.html', {
        'student': student,
        'my_batches': my_batches,
    })


@student_required
def student_profile(request):
    try:
        student = request.user.student
    except Exception:
        return render(request, 'student_portal/no_profile.html', {})
    return render(request, 'student_portal/profile.html', {'student': student})
