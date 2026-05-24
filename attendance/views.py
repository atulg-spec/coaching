from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Q
from .models import AttendanceSession, AttendanceRecord, StaffAttendance
from batches.models import Batch
from students.models import Student
from accounts.decorators import staff_or_admin_required, admin_required
import datetime


@staff_or_admin_required
def mark_attendance(request, batch_id):
    batch = get_object_or_404(Batch, pk=batch_id)
    user = request.user

    # Staff can only mark attendance for their OWN batches
    if user.role == 'staff':
        try:
            if batch.teacher.user != user:
                messages.error(request, "You can only mark attendance for batches assigned to you.")
                return redirect('dashboard_home')
        except Exception:
            messages.error(request, "You are not assigned to any batch.")
            return redirect('dashboard_home')

    today = timezone.now().date()
    session, created = AttendanceSession.objects.get_or_create(
        batch=batch, date=today,
        defaults={'marked_by': user}
    )
    students = batch.students.filter(is_active=True)

    if request.method == 'POST':
        session.topic_covered = request.POST.get('topic_covered', '')
        session.save()
        for student in students:
            status = request.POST.get(f'status_{student.id}', 'absent')
            remarks = request.POST.get(f'remarks_{student.id}', '')
            record, _ = AttendanceRecord.objects.get_or_create(session=session, student=student)
            record.status = status
            record.remarks = remarks
            record.save()
        messages.success(request, f"Attendance saved for {batch.batch_name} on {today}.")
        return redirect('attendance_reports')

    existing_records = {r.student_id: r for r in session.records.all()}
    student_data = [
        {'student': s, 'record': existing_records.get(s.id)}
        for s in students
    ]

    return render(request, 'dashboard/attendance/mark.html', {
        'batch': batch,
        'today': today,
        'session': session,
        'student_data': student_data,
    })


@staff_or_admin_required
def attendance_reports(request):
    user = request.user
    if user.role == 'admin':
        batches = Batch.objects.filter(is_active=True)
    else:
        try:
            batches = Batch.objects.filter(teacher=user.staff, is_active=True)
        except Exception:
            batches = Batch.objects.none()

    selected_batch_id = request.GET.get('batch')
    selected_date_str = request.GET.get('date')

    sessions = AttendanceSession.objects.select_related('batch').order_by('-date')
    student_summary = None
    selected_batch = None
    date_session = None

    if selected_batch_id:
        selected_batch = get_object_or_404(Batch, pk=selected_batch_id)
        # Staff cannot view other batches' reports
        if user.role == 'staff' and selected_batch not in batches:
            messages.error(request, "You can only view reports for your own batches.")
            return redirect('attendance_reports')

        sessions = sessions.filter(batch=selected_batch)
        all_students = selected_batch.students.filter(is_active=True)
        total_sessions = sessions.count()

        student_summary = []
        for student in all_students:
            qs = AttendanceRecord.objects.filter(session__batch=selected_batch, student=student)
            present = qs.filter(status='present').count()
            absent  = qs.filter(status='absent').count()
            late    = qs.filter(status='late').count()
            leave   = qs.filter(status='leave').count()
            pct = round((present / total_sessions * 100), 1) if total_sessions > 0 else 0
            student_summary.append({
                'student': student, 'present': present,
                'absent': absent, 'late': late, 'leave': leave,
                'total': total_sessions, 'percentage': pct,
            })

    if selected_batch_id and selected_date_str:
        try:
            sel_date = datetime.date.fromisoformat(selected_date_str)
            date_session = AttendanceSession.objects.filter(
                batch_id=selected_batch_id, date=sel_date
            ).prefetch_related('records__student__user').first()
        except ValueError:
            date_session = None

    if selected_batch_id:
        recent_sessions = AttendanceSession.objects.filter(
            batch_id=selected_batch_id
        ).select_related('batch', 'marked_by').order_by('-date')
    elif user.role == 'staff':
        recent_sessions = AttendanceSession.objects.filter(
            batch__in=batches
        ).select_related('batch', 'marked_by').order_by('-date')[:15]
    else:
        recent_sessions = AttendanceSession.objects.select_related('batch', 'marked_by').order_by('-date')[:15]

    return render(request, 'dashboard/attendance/reports.html', {
        'batches': batches,
        'selected_batch': selected_batch,
        'selected_batch_id': selected_batch_id,
        'selected_date': selected_date_str,
        'student_summary': student_summary,
        'date_session': date_session,
        'recent_sessions': recent_sessions,
        'today': timezone.now().date(),
    })


@staff_or_admin_required
def student_attendance(request, student_id):
    student = get_object_or_404(Student, pk=student_id)
    records = AttendanceRecord.objects.filter(
        student=student
    ).select_related('session__batch').order_by('-session__date')

    batch_stats = []
    for batch in student.batches.filter(is_active=True):
        total   = AttendanceRecord.objects.filter(student=student, session__batch=batch).count()
        present = AttendanceRecord.objects.filter(student=student, session__batch=batch, status='present').count()
        pct = round((present / total * 100), 1) if total > 0 else 0
        batch_stats.append({'batch': batch, 'total': total, 'present': present, 'percentage': pct})

    return render(request, 'dashboard/attendance/student.html', {
        'student': student,
        'records': records[:30],
        'batch_stats': batch_stats,
    })

@admin_required
def mark_staff_attendance(request):
    today = timezone.now().date()
    date_str = request.GET.get('date', str(today))
    
    try:
        selected_date = datetime.date.fromisoformat(date_str)
    except ValueError:
        selected_date = today

    from staff.models import Staff
    staff_members = Staff.objects.filter(is_active=True)
    
    if request.method == 'POST':
        selected_date_post = request.POST.get('date', str(today))
        try:
            date_to_save = datetime.date.fromisoformat(selected_date_post)
        except ValueError:
            date_to_save = today

        for staff in staff_members:
            status = request.POST.get(f'status_{staff.id}', 'present')
            in_time_val = request.POST.get(f'in_time_{staff.id}')
            out_time_val = request.POST.get(f'out_time_{staff.id}')

            # handle empty time strings
            in_time = in_time_val if in_time_val else None
            out_time = out_time_val if out_time_val else None

            record, _ = StaffAttendance.objects.get_or_create(
                staff=staff, date=date_to_save,
                defaults={'marked_by': request.user}
            )
            record.status = status
            record.in_time = in_time
            record.out_time = out_time
            if not record.marked_by:
                record.marked_by = request.user
            record.save()
        
        messages.success(request, f"Staff attendance saved for {date_to_save}.")
        from django.urls import reverse
        return redirect(f"{reverse('staff_attendance_reports')}?date={date_to_save}")

    existing_records = {r.staff_id: r for r in StaffAttendance.objects.filter(date=selected_date)}
    staff_data = [
        {'staff': s, 'record': existing_records.get(s.id)}
        for s in staff_members
    ]

    return render(request, 'dashboard/attendance/staff_mark.html', {
        'selected_date': selected_date,
        'staff_data': staff_data,
    })

@admin_required
def staff_attendance_reports(request):
    selected_date_str = request.GET.get('date')
    selected_staff_id = request.GET.get('staff_id')
    
    from staff.models import Staff
    staff_members = Staff.objects.filter(is_active=True)
    
    recent_records = StaffAttendance.objects.select_related('staff__user').order_by('-date', 'staff__user__first_name')
    
    if selected_date_str:
        try:
            sel_date = datetime.date.fromisoformat(selected_date_str)
            recent_records = recent_records.filter(date=sel_date)
        except ValueError:
            pass

    if selected_staff_id:
        recent_records = recent_records.filter(staff_id=selected_staff_id)

    return render(request, 'dashboard/attendance/staff_reports.html', {
        'recent_records': recent_records[:100],
        'staff_members': staff_members,
        'selected_date': selected_date_str,
        'selected_staff_id': selected_staff_id,
    })
