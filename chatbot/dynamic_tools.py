"""
Generic, composable ERP Database Query Tools for Natasha Agent.
Executes pure, read-only Django ORM operations with parameter validation.
Provides dynamic filtering, multi-module joins, aggregations, and comparisons.
"""

from decimal import Decimal
from datetime import date, timedelta
from django.db.models import Sum, Count, Q, F, Avg
from django.utils import timezone

from students.models import Student
from batches.models import Batch, Subject
from payments.models import Payment, PaymentTransaction, Inquiry, StaffSalary
from attendance.models import AttendanceRecord, AttendanceSession
from staff.models import Staff


def format_inr(val):
    if val is None:
        return "₹0"
    try:
        n = int(round(float(val)))
        return f"₹{n:,}"
    except Exception:
        return f"₹{val}"


# ==============================================================================
# 1. DYNAMIC STUDENT QUERY TOOL
# ==============================================================================

def query_students(
    is_active=None,
    current_class=None,
    board=None,
    search=None,
    parent_phone_duplicate=False,
    has_pending_fees=None,
    min_pending_amount=None,
    attendance_below=None,
    admission_days_ago=None,
    admission_month=None,
    admission_year=None,
    admission_date_from=None,
    admission_date_to=None,
    batch_name=None,
    student_ids=None,
    limit=50,
    **kwargs
):
    """
    General-purpose student records query tool.
    Supports complex combined conditions across enrollment, fees, attendance, and parent info.
    """
    qs = Student.objects.all().select_related('user')

    # Status filter
    if is_active is not None:
        if isinstance(is_active, str):
            is_active = is_active.lower() in ['true', '1', 'yes', 'active']
        qs = qs.filter(is_active=bool(is_active))

    # Class filter
    if current_class and str(current_class).lower() not in ['all', 'any']:
        clean_cls = str(current_class).lower().replace('class', '').replace('grade', '').strip()
        qs = qs.filter(current_class=clean_cls)

    # Board filter
    if board and str(board).lower() not in ['all', 'any']:
        qs = qs.filter(board__iexact=str(board).strip())

    # Batch name filter
    if batch_name:
        qs = qs.filter(batches__batch_name__icontains=str(batch_name).strip()).distinct()

    # ID list filter (from conversational context)
    if student_ids:
        qs = qs.filter(id__in=student_ids)

    # Search query
    if search:
        s = str(search).strip()
        qs = qs.filter(
            Q(user__first_name__icontains=s) |
            Q(user__last_name__icontains=s) |
            Q(user__username__icontains=s) |
            Q(student_id__icontains=s) |
            Q(parent_name__icontains=s) |
            Q(parent_phone__icontains=s)
        )

    # Duplicate parent phone filter
    if parent_phone_duplicate:
        duplicate_phones = Student.objects.values('parent_phone').annotate(
            c=Count('id')
        ).filter(c__gt=1).values_list('parent_phone', flat=True)
        qs = qs.filter(parent_phone__in=duplicate_phones)

    # Admission date filters
    today = timezone.now().date()
    if admission_days_ago is not None:
        cutoff = today - timedelta(days=int(admission_days_ago))
        qs = qs.filter(admission_date__gte=cutoff)
    if admission_month:
        qs = qs.filter(admission_date__month=int(admission_month))
    if admission_year:
        qs = qs.filter(admission_date__year=int(admission_year))
    if admission_date_from:
        qs = qs.filter(admission_date__gte=admission_date_from)
    if admission_date_to:
        qs = qs.filter(admission_date__lte=admission_date_to)

    # Fee-based student filters
    if has_pending_fees or min_pending_amount is not None:
        pending_payments = Payment.objects.filter(status__in=['pending', 'partial'])
        student_pending_totals = pending_payments.values('student_id').annotate(
            total_due=Sum(F('amount_due') - F('amount_paid'))
        )
        if min_pending_amount is not None:
            min_dec = Decimal(str(min_pending_amount))
            eligible_sids = [p['student_id'] for p in student_pending_totals if (p['total_due'] or 0) >= min_dec]
        else:
            eligible_sids = [p['student_id'] for p in student_pending_totals if (p['total_due'] or 0) > 0]
        qs = qs.filter(id__in=eligible_sids)

    # Attendance-based student filters
    if attendance_below is not None:
        thresh = float(attendance_below)
        if thresh > 1.0:
            thresh = thresh / 100.0  # normalize 75 to 0.75

        student_att = AttendanceRecord.objects.values('student_id').annotate(
            total=Count('id'),
            present=Count('id', filter=Q(status='present'))
        )
        low_att_ids = []
        for a in student_att:
            if a['total'] > 0 and (a['present'] / a['total']) < thresh:
                low_att_ids.append(a['student_id'])
        qs = qs.filter(id__in=low_att_ids)

    total_count = qs.count()
    limited_qs = list(qs[:limit])
    limited_ids = [s.id for s in limited_qs]

    # Pre-calculate dues and attendance for retrieved students
    dues_map = {}
    p_qs = Payment.objects.filter(
        student_id__in=limited_ids, status__in=['pending', 'partial']
    ).values('student_id').annotate(due=Sum(F('amount_due') - F('amount_paid')))
    for p in p_qs:
        dues_map[p['student_id']] = float(p['due'] or 0)

    att_map = {}
    a_qs = AttendanceRecord.objects.filter(student_id__in=limited_ids).values('student_id').annotate(
        total=Count('id'),
        present=Count('id', filter=Q(status='present'))
    )
    for a in a_qs:
        if a['total'] > 0:
            att_map[a['student_id']] = round((a['present'] / a['total']) * 100, 1)

    records = []
    for s in limited_qs:
        records.append({
            "id": s.id,
            "name": s.user.get_full_name() or s.user.username,
            "student_id": s.student_id,
            "current_class": s.current_class,
            "board": s.board,
            "school_name": s.school_name,
            "parent_name": s.parent_name,
            "parent_phone": s.parent_phone,
            "parent_email": s.parent_email,
            "address": s.address,
            "admission_date": str(s.admission_date),
            "is_active": s.is_active,
            "pending_due": dues_map.get(s.id, 0.0),
            "attendance_pct": att_map.get(s.id),
            "profile_url": f"/dashboard/students/{s.id}/"
        })

    return {
        "success": True,
        "total_matched": total_count,
        "count_returned": len(records),
        "total_pending_due_sum": sum(r["pending_due"] for r in records),
        "students": records,
        "student_ids": [r["id"] for r in records]
    }


# ==============================================================================
# 2. DYNAMIC PAYMENT & FEE QUERY TOOL
# ==============================================================================

def query_payments(
    status=None,
    student_name=None,
    student_id=None,
    student_ids=None,
    current_class=None,
    batch_id=None,
    min_balance=None,
    overdue_days=None,
    month_from=None,
    month_to=None,
    months_ago=None,
    aggregate_by=None,
    limit=50,
    **kwargs
):
    """
    General-purpose fee, dues, and collections query tool.
    Supports itemized records or aggregations by class, batch, month, student, or payment_mode.
    """
    qs = Payment.objects.all().select_related('student__user', 'batch')

    # Status filter
    if status and status != 'all':
        if status == 'collected':
            qs = qs.filter(amount_paid__gt=0)
        elif status == 'pending':
            qs = qs.filter(status__in=['pending', 'partial'])
        else:
            if isinstance(status, str):
                status = [status]
            qs = qs.filter(status__in=status)

    # Student filter
    if student_ids:
        qs = qs.filter(student_id__in=student_ids)
    elif student_id:
        qs = qs.filter(student_id=student_id)
    elif student_name:
        s_clean = str(student_name).strip()
        qs = qs.filter(
            Q(student__user__first_name__icontains=s_clean) |
            Q(student__user__last_name__icontains=s_clean) |
            Q(student__student_id__icontains=s_clean)
        )

    # Class filter
    if current_class and str(current_class).lower() not in ['all', 'any']:
        clean_cls = str(current_class).lower().replace('class', '').strip()
        qs = qs.filter(student__current_class=clean_cls)

    # Batch filter
    if batch_id:
        qs = qs.filter(batch_id=batch_id)

    # Overdue days filter
    today = timezone.now().date()
    if overdue_days is not None:
        cutoff = today - timedelta(days=int(overdue_days))
        qs = qs.filter(status__in=['pending', 'partial'], month__lte=cutoff)

    # Date / Month range filters
    if months_ago is not None:
        start_date = today - timedelta(days=int(months_ago) * 30)
        qs = qs.filter(month__gte=start_date)
    if month_from:
        qs = qs.filter(month__gte=month_from)
    if month_to:
        qs = qs.filter(month__lte=month_to)

    # Min balance filter
    if min_balance is not None:
        qs = qs.filter(status__in=['pending', 'partial'])

    # AGGREGATIONS
    if aggregate_by == 'class':
        agg = qs.values('student__current_class').annotate(
            total_due=Sum('amount_due'),
            total_paid=Sum('amount_paid'),
            total_balance=Sum(F('amount_due') - F('amount_paid')),
            student_count=Count('student', distinct=True)
        ).order_by('-total_balance')
        agg_list = [
            {
                "student__current_class": a["student__current_class"],
                "total_due": float(a["total_due"] or 0),
                "total_paid": float(a["total_paid"] or 0),
                "total_balance": float(a["total_balance"] or 0),
                "student_count": a["student_count"],
            }
            for a in agg
        ]
        return {
            "success": True,
            "aggregation": "class",
            "results": agg_list,
            "total_due_sum": sum(a["total_due"] for a in agg_list),
            "total_paid_sum": sum(a["total_paid"] for a in agg_list),
            "total_balance_sum": sum(a["total_balance"] for a in agg_list),
        }

    if aggregate_by == 'batch':
        agg = qs.values('batch__id', 'batch__batch_name', 'batch__class_level').annotate(
            total_due=Sum('amount_due'),
            total_paid=Sum('amount_paid'),
            total_balance=Sum(F('amount_due') - F('amount_paid')),
            student_count=Count('student', distinct=True)
        ).order_by('-total_balance')
        agg_list = [
            {
                "batch__id": a["batch__id"],
                "batch__batch_name": a["batch__batch_name"],
                "batch__class_level": a["batch__class_level"],
                "total_due": float(a["total_due"] or 0),
                "total_paid": float(a["total_paid"] or 0),
                "total_balance": float(a["total_balance"] or 0),
                "student_count": a["student_count"],
            }
            for a in agg
        ]
        return {
            "success": True,
            "aggregation": "batch",
            "results": agg_list,
            "total_due_sum": sum(a["total_due"] for a in agg_list),
            "total_paid_sum": sum(a["total_paid"] for a in agg_list),
            "total_balance_sum": sum(a["total_balance"] for a in agg_list),
        }

    if aggregate_by == 'month':
        agg = qs.values('month').annotate(
            total_due=Sum('amount_due'),
            total_paid=Sum('amount_paid'),
            total_balance=Sum(F('amount_due') - F('amount_paid')),
            student_count=Count('student', distinct=True)
        ).order_by('-month')
        agg_list = [
            {
                "month": str(a["month"]),
                "total_due": float(a["total_due"] or 0),
                "total_paid": float(a["total_paid"] or 0),
                "total_balance": float(a["total_balance"] or 0),
                "student_count": a["student_count"],
            }
            for a in agg
        ]
        return {
            "success": True,
            "aggregation": "month",
            "results": agg_list,
            "total_due_sum": sum(a["total_due"] for a in agg_list),
            "total_paid_sum": sum(a["total_paid"] for a in agg_list),
            "total_balance_sum": sum(a["total_balance"] for a in agg_list),
        }

    if aggregate_by == 'payment_mode':
        agg = qs.values('payment_mode').annotate(
            total_paid=Sum('amount_paid'),
            record_count=Count('id')
        ).order_by('-total_paid')
        agg_list = [
            {
                "payment_mode": a["payment_mode"] or "unspecified",
                "total_paid": float(a["total_paid"] or 0),
                "record_count": a["record_count"],
            }
            for a in agg
        ]
        return {
            "success": True,
            "aggregation": "payment_mode",
            "results": agg_list,
            "total_paid_sum": sum(a["total_paid"] for a in agg_list),
        }

    if aggregate_by == 'student':
        agg = qs.values(
            'student__id',
            'student__user__first_name',
            'student__user__last_name',
            'student__student_id',
            'student__current_class',
            'student__board',
            'student__parent_name',
            'student__parent_phone'
        ).annotate(
            total_due=Sum('amount_due'),
            total_paid=Sum('amount_paid'),
            total_balance=Sum(F('amount_due') - F('amount_paid'))
        ).order_by('-total_balance')

        if min_balance is not None:
            min_dec = Decimal(str(min_balance))
            agg = [a for a in agg if (a['total_balance'] or 0) >= min_dec]
        else:
            agg = list(agg)

        students_out = []
        for a in agg:
            students_out.append({
                "student__id": a["student__id"],
                "student__user__first_name": a["student__user__first_name"],
                "student__user__last_name": a["student__user__last_name"],
                "student__student_id": a["student__student_id"],
                "student__current_class": a["student__current_class"],
                "student__board": a["student__board"],
                "student__parent_name": a["student__parent_name"],
                "student__parent_phone": a["student__parent_phone"],
                "total_due": float(a["total_due"] or 0),
                "total_paid": float(a["total_paid"] or 0),
                "total_balance": float(a["total_balance"] or 0),
            })

        return {
            "success": True,
            "aggregation": "student",
            "student_count": len(students_out),
            "total_due_sum": sum(a["total_due"] for a in students_out),
            "total_paid_sum": sum(a["total_paid"] for a in students_out),
            "total_balance_sum": sum(a["total_balance"] for a in students_out),
            "students": students_out[:limit],
            "student_ids": [a["student__id"] for a in students_out]
        }

    # Itemized records
    total_due_sum = qs.aggregate(s=Sum('amount_due'))['s'] or Decimal('0.00')
    total_paid_sum = qs.aggregate(s=Sum('amount_paid'))['s'] or Decimal('0.00')
    balance_sum = total_due_sum - total_paid_sum

    records = []
    for p in qs[:limit]:
        b = p.amount_due - p.amount_paid
        records.append({
            "id": p.id,
            "student_id": p.student_id,
            "student_name": p.student.user.get_full_name(),
            "student_code": p.student.student_id,
            "current_class": p.student.current_class,
            "parent_name": p.student.parent_name,
            "parent_phone": p.student.parent_phone,
            "batch_name": p.batch.batch_name,
            "month": str(p.month),
            "amount_due": float(p.amount_due),
            "amount_paid": float(p.amount_paid),
            "balance": float(b),
            "status": p.status,
            "receipt_number": p.receipt_number or "",
            "payment_mode": p.payment_mode or ""
        })

    return {
        "success": True,
        "total_records": qs.count(),
        "total_due_sum": float(total_due_sum),
        "total_paid_sum": float(total_paid_sum),
        "total_balance_sum": float(balance_sum),
        "records": records,
        "student_ids": list(set(r["student_id"] for r in records))
    }


# ==============================================================================
# 3. DYNAMIC ATTENDANCE QUERY TOOL
# ==============================================================================

def query_attendance(
    date_val=None,
    date_from=None,
    date_to=None,
    status=None,
    current_class=None,
    student_id=None,
    threshold_below=None,
    aggregate_by=None,
    limit=50,
    **kwargs
):
    """
    General-purpose attendance analysis tool.
    Supports session roll calls, absentee lists, and student attendance rate computations.
    """
    today = timezone.now().date()
    records_qs = AttendanceRecord.objects.all().select_related('student__user', 'session__batch')

    if date_val:
        records_qs = records_qs.filter(session__date=date_val)
    elif not date_from and not date_to:
        # Default to today if no dates specified
        records_qs = records_qs.filter(session__date=today)

    if date_from:
        records_qs = records_qs.filter(session__date__gte=date_from)
    if date_to:
        records_qs = records_qs.filter(session__date__lte=date_to)

    if status and status != 'all':
        records_qs = records_qs.filter(status=status)

    if current_class and current_class not in ['all', 'any']:
        clean_cls = str(current_class).replace('class', '').strip()
        records_qs = records_qs.filter(student__current_class=clean_cls)

    if student_id:
        records_qs = records_qs.filter(student_id=student_id)

    # Check if sessions exist
    sessions = AttendanceSession.objects.all()
    if date_val:
        sessions = sessions.filter(date=date_val)
    latest_session = AttendanceSession.objects.order_by('-date').first()

    total_records = records_qs.count()
    present_count = records_qs.filter(status='present').count()
    absent_count = records_qs.filter(status='absent').count()
    rate = (present_count / total_records * 100) if total_records > 0 else 0

    items = []
    for r in records_qs[:limit]:
        items.append({
            "student_name": r.student.user.get_full_name(),
            "student_id": r.student_id,
            "current_class": r.student.current_class,
            "batch_name": r.session.batch.batch_name,
            "date": str(r.session.date),
            "status": r.status,
            "parent_name": r.student.parent_name,
            "parent_phone": r.student.parent_phone
        })

    return {
        "success": True,
        "date_queried": str(date_val or today),
        "total_records": total_records,
        "present_count": present_count,
        "absent_count": absent_count,
        "attendance_rate": round(rate, 1),
        "sessions_marked": sessions.count(),
        "latest_session_date": str(latest_session.date) if latest_session else None,
        "items": items,
        "student_ids": list(set(r["student_id"] for r in items))
    }


# ==============================================================================
# 4. DYNAMIC BATCHES & ACADEMIC TOOL
# ==============================================================================

def query_batches(
    class_level=None,
    board=None,
    is_active=True,
    compute_ratio=False,
    teacher_name=None,
    limit=50,
    **kwargs
):
    """
    General-purpose batches, timetable, and capacity analysis tool.
    Computes student-to-faculty ratios and batch seat capacity utilization.
    """
    qs = Batch.objects.all().select_related('teacher__user').prefetch_related('students')

    if is_active is not None:
        qs = qs.filter(is_active=bool(is_active))
    if class_level and class_level not in ['all', 'any']:
        clean_cls = str(class_level).replace('class', '').strip()
        qs = qs.filter(class_level=clean_cls)
    if board and board not in ['all', 'any']:
        qs = qs.filter(board__iexact=str(board).strip())
    if teacher_name:
        qs = qs.filter(
            Q(teacher__user__first_name__icontains=teacher_name) |
            Q(teacher__user__last_name__icontains=teacher_name)
        )

    batches = []
    for b in qs:
        st_count = b.students.filter(is_active=True).count()
        utilization = (st_count / b.max_students * 100) if b.max_students else 0
        batches.append({
            "id": b.id,
            "batch_name": b.batch_name,
            "batch_code": b.batch_code,
            "class_level": b.class_level,
            "board": b.board,
            "teacher": b.teacher.user.get_full_name() if b.teacher else "Unassigned",
            "enrolled_students": st_count,
            "max_students": b.max_students,
            "utilization_pct": round(utilization, 1),
            "ratio_students_per_faculty": st_count,  # 1 teacher per batch
            "monthly_fee": float(b.monthly_fee),
            "days": b.get_days_display(),
            "time": f"{b.start_time.strftime('%I:%M %p')} - {b.end_time.strftime('%I:%M %p')}"
        })

    if compute_ratio:
        batches.sort(key=lambda x: x["enrolled_students"], reverse=True)

    return {
        "success": True,
        "total_batches": len(batches),
        "batches": batches[:limit]
    }


# ==============================================================================
# 5. DYNAMIC STAFF & PAYROLL TOOL
# ==============================================================================

def query_staff(is_active=None, designation=None, subject_expertise=None, limit=50, **kwargs):
    """General-purpose staff and faculty directory query tool."""
    qs = Staff.objects.all().select_related('user')
    if is_active is not None:
        qs = qs.filter(is_active=bool(is_active))
    if designation:
        qs = qs.filter(designation__icontains=designation)
    if subject_expertise:
        qs = qs.filter(subject_expertise__icontains=subject_expertise)

    total_salary = qs.aggregate(s=Sum('salary'))['s'] or Decimal('0.00')

    staff_list = []
    for s in qs[:limit]:
        staff_list.append({
            "name": s.user.get_full_name() or s.user.username,
            "employee_id": s.employee_id,
            "designation": s.designation,
            "subject": s.subject_expertise,
            "phone": s.user.phone or "N/A",
            "email": s.user.email or "N/A",
            "salary": float(s.salary),
            "is_active": s.is_active
        })

    return {
        "success": True,
        "total_staff": qs.count(),
        "total_monthly_payroll": float(total_salary),
        "staff": staff_list
    }


# ==============================================================================
# 6. DYNAMIC INQUIRIES & LEADS TOOL
# ==============================================================================

def query_inquiries(is_followed_up=None, interested_class=None, limit=50, **kwargs):
    """General-purpose inquiries and admissions leads tool."""
    qs = Inquiry.objects.all().order_by('-submitted_at')
    if is_followed_up is not None:
        qs = qs.filter(is_followed_up=bool(is_followed_up))
    if interested_class:
        qs = qs.filter(interested_class__icontains=interested_class)

    items = []
    for i in qs[:limit]:
        items.append({
            "name": i.name,
            "phone": i.phone,
            "email": i.email,
            "interested_class": i.interested_class,
            "submitted_at": i.submitted_at.strftime('%d %b %Y'),
            "is_followed_up": i.is_followed_up
        })

    return {
        "success": True,
        "total": qs.count(),
        "pending_followup": qs.filter(is_followed_up=False).count(),
        "inquiries": items
    }


# ==============================================================================
# 7. INSTITUTE OVERVIEW TOOL
# ==============================================================================

def get_institute_overview(**kwargs):
    """
    Returns a live high-level snapshot of the entire coaching institute across modules.
    Useful for broad executive questions and date-aware reasoning.
    """
    today = timezone.now().date()
    active_students = Student.objects.filter(is_active=True).count()
    inactive_students = Student.objects.filter(is_active=False).count()
    active_batches = Batch.objects.filter(is_active=True).count()
    active_staff = Staff.objects.filter(is_active=True).count()
    pending_inquiries = Inquiry.objects.filter(is_followed_up=False).count()

    fee_agg = Payment.objects.aggregate(
        billed=Sum('amount_due'),
        collected=Sum('amount_paid'),
    )
    billed = float(fee_agg['billed'] or 0)
    collected = float(fee_agg['collected'] or 0)
    pending = max(0.0, billed - collected)

    today_att = AttendanceRecord.objects.filter(session__date=today)
    today_total = today_att.count()
    today_present = today_att.filter(status='present').count()

    return {
        "success": True,
        "today_date": str(today),
        "current_month": today.month,
        "current_year": today.year,
        "active_students": active_students,
        "inactive_students": inactive_students,
        "total_students": active_students + inactive_students,
        "active_batches": active_batches,
        "active_staff": active_staff,
        "pending_inquiries": pending_inquiries,
        "fees_total_billed": billed,
        "fees_total_collected": collected,
        "fees_total_pending": pending,
        "today_attendance_marked": today_total,
        "today_attendance_present": today_present,
        "available_erp_modules": [
            "Student profiles & parent contacts",
            "Fee registers, installments & payment transactions",
            "Student & staff attendance",
            "Batches, subjects & study materials",
            "Staff directory & salaries",
            "Admissions inquiries",
        ],
        "unavailable_modules": [
            "Exam records, test scores & student marks/grades (not in current ERP schema)"
        ],
    }


# ==============================================================================
# 8. TOOL REGISTRY & DISPATCHER
# ==============================================================================

TOOL_REGISTRY = {
    "query_students": query_students,
    "query_payments": query_payments,
    "query_attendance": query_attendance,
    "query_batches": query_batches,
    "query_staff": query_staff,
    "query_inquiries": query_inquiries,
    "get_institute_overview": get_institute_overview,
}

TOOL_DEFINITIONS = [
    {
        "name": "query_students",
        "description": "Search or filter student profiles by active status, class level, board, name/phone search, batch, student_ids, duplicate parent phones, pending fee flags, low attendance flags, and admission dates/months.",
        "parameters": {
            "type": "object",
            "properties": {
                "is_active": {"type": "boolean", "description": "True for currently enrolled active students, False for inactive."},
                "current_class": {"type": "string", "description": "Class level, e.g. '8', '9', '10', '11', '12'."},
                "board": {"type": "string", "description": "'CBSE' or 'ICSE'."},
                "batch_name": {"type": "string", "description": "Filter by batch name."},
                "student_ids": {"type": "array", "items": {"type": "integer"}, "description": "Specific internal student IDs from previous tool results or context."},
                "search": {"type": "string", "description": "Search keyword for student name, student ID, parent name, or phone number."},
                "parent_phone_duplicate": {"type": "boolean", "description": "True to find students whose parents share the same registered mobile number (siblings)."},
                "has_pending_fees": {"type": "boolean", "description": "True to filter students who have pending/partial fees."},
                "min_pending_amount": {"type": "number", "description": "Filter students with pending fee dues >= this amount (e.g. 5000)."},
                "attendance_below": {"type": "number", "description": "Filter students with attendance rate below threshold (e.g. 75.0 or 0.75)."},
                "admission_days_ago": {"type": "integer", "description": "Filter students admitted within the last N days (e.g. 60)."},
                "admission_month": {"type": "integer", "description": "Filter by admission month (1-12)."},
                "admission_year": {"type": "integer", "description": "Filter by admission year (e.g. 2026)."},
                "admission_date_from": {"type": "string", "description": "YYYY-MM-DD start date."},
                "admission_date_to": {"type": "string", "description": "YYYY-MM-DD end date."}
            }
        }
    },
    {
        "name": "query_payments",
        "description": "Inspect fee registers, calculate dues, analyze collections, or aggregate balances by class, batch, month, payment_mode, or student.",
        "parameters": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["pending", "paid", "partial", "collected", "all"], "description": "Payment status ('pending' includes unpaid & partial; 'collected' includes any with amount_paid > 0)."},
                "student_name": {"type": "string", "description": "Name or ID of specific student."},
                "student_ids": {"type": "array", "items": {"type": "integer"}, "description": "List of student IDs from context or previous query."},
                "current_class": {"type": "string", "description": "Class level, e.g. '10'."},
                "overdue_days": {"type": "integer", "description": "Find payments overdue by more than N days (e.g. 30)."},
                "min_balance": {"type": "number", "description": "Filter by minimum outstanding balance (e.g. 5000)."},
                "months_ago": {"type": "integer", "description": "Filter payments from last N months (e.g. 3)."},
                "month_from": {"type": "string", "description": "YYYY-MM-DD start month."},
                "month_to": {"type": "string", "description": "YYYY-MM-DD end month."},
                "aggregate_by": {"type": "string", "enum": ["class", "batch", "student", "month", "payment_mode"], "description": "Group and rank results."}
            }
        }
    },
    {
        "name": "query_attendance",
        "description": "Inspect roll call records, absentees on a date or date range, attendance percentages, and low attendance students.",
        "parameters": {
            "type": "object",
            "properties": {
                "date_val": {"type": "string", "description": "Specific date in 'YYYY-MM-DD' format (defaults to today if omitted and no range given)."},
                "date_from": {"type": "string", "description": "Start date 'YYYY-MM-DD'."},
                "date_to": {"type": "string", "description": "End date 'YYYY-MM-DD'."},
                "status": {"type": "string", "enum": ["absent", "present", "late", "all"]},
                "current_class": {"type": "string", "description": "Class level."},
                "threshold_below": {"type": "number", "description": "Attendance percentage threshold (e.g. 75)."}
            }
        }
    },
    {
        "name": "query_batches",
        "description": "Retrieve academic batches, timetables, assigned faculty, and compute student-to-faculty ratios or seat utilization.",
        "parameters": {
            "type": "object",
            "properties": {
                "class_level": {"type": "string", "description": "Class level, e.g. '10'."},
                "compute_ratio": {"type": "boolean", "description": "True to calculate and rank batches by student strength and faculty ratio."},
                "teacher_name": {"type": "string", "description": "Search by teacher name."}
            }
        }
    },
    {
        "name": "query_staff",
        "description": "Query staff directory, designations, qualifications, and faculty payroll totals.",
        "parameters": {
            "type": "object",
            "properties": {
                "designation": {"type": "string", "description": "e.g. 'Senior Faculty'"},
                "is_active": {"type": "boolean"}
            }
        }
    },
    {
        "name": "query_inquiries",
        "description": "Check prospective student leads, pending follow-ups, and admissions inquiries.",
        "parameters": {
            "type": "object",
            "properties": {
                "is_followed_up": {"type": "boolean", "description": "False for leads pending follow-up."},
                "interested_class": {"type": "string"}
            }
        }
    },
    {
        "name": "get_institute_overview",
        "description": "Get a live high-level summary of the entire institute (student counts, batches, staff, fees billed/collected/pending, today's attendance, and available/unavailable modules).",
        "parameters": {"type": "object", "properties": {}}
    }
]


def execute_tool(tool_name: str, parameters: dict) -> dict:
    """Executes a tool by name with validated parameters."""
    func = TOOL_REGISTRY.get(tool_name)
    if not func:
        return {"success": False, "error": f"Unknown tool: '{tool_name}'"}
    try:
        clean_params = {k: v for k, v in parameters.items() if v is not None}
        return func(**clean_params)
    except Exception as e:
        return {"success": False, "error": f"Tool execution error: {str(e)}"}
