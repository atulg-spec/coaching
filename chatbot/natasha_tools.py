"""
Natasha ERP Database Query Layer.
Provides secure, read-only Django ORM operations with parameter validation.
Directly accesses actual institute records for student management, fee registers,
parent contacts, attendance, batches, and staff.
"""

from decimal import Decimal
from datetime import date, timedelta
from django.db.models import Sum, Count, Q, F, Avg
from django.utils import timezone
from django.urls import reverse

from students.models import Student
from batches.models import Batch, Subject
from payments.models import Payment, PaymentTransaction, Inquiry, StaffSalary
from attendance.models import AttendanceRecord, AttendanceSession
from staff.models import Staff


def format_currency(amount):
    """Formats a decimal or int as Indian Rupee (e.g., ₹1,25,000 or ₹5,000)."""
    if amount is None:
        return "₹0"
    try:
        val = int(round(float(amount)))
        # Format with commas
        return f"₹{val:,}"
    except Exception:
        return f"₹{amount}"


# ==============================================================================
# 1. STUDENT MANAGEMENT TOOLS
# ==============================================================================

def get_student_enrollment_stats(class_level=None, board=None):
    """
    Returns total, active, and inactive student counts, plus class breakdown.
    """
    qs = Student.objects.all()
    if class_level:
        qs = qs.filter(current_class=str(class_level))
    if board:
        qs = qs.filter(board__iexact=board)

    total_count = qs.count()
    active_count = qs.filter(is_active=True).count()
    inactive_count = total_count - active_count

    # Breakdown by class
    class_breakdown = qs.filter(is_active=True).values('current_class').annotate(
        count=Count('id')
    ).order_by('current_class')

    # Breakdown by board
    board_breakdown = qs.filter(is_active=True).values('board').annotate(
        count=Count('id')
    ).order_by('board')

    kpis = [
        {"label": "Active Students", "value": str(active_count), "color": "emerald"},
        {"label": "Total Registered", "value": str(total_count), "color": "blue"},
        {"label": "Inactive / Left", "value": str(inactive_count), "color": "slate"},
    ]

    # Markdown representation
    md = [
        f"### 🎓 Student Enrollment Summary",
        f"- **Active Students Currently Enrolled:** **{active_count}**",
        f"- **Total Registered Records:** **{total_count}**",
        f"- **Inactive / Graduated:** **{inactive_count}**",
        "",
        "#### **Active Students by Class:**",
        "| Class | Active Students | Board Breakdown |",
        "| :--- | :---: | :--- |"
    ]

    for item in class_breakdown:
        c_lvl = item['current_class']
        c_count = item['count']
        c_boards = qs.filter(is_active=True, current_class=c_lvl).values('board').annotate(bc=Count('id'))
        b_str = ", ".join([f"{b['board']}: {b['bc']}" for b in c_boards])
        md.append(f"| Class {c_lvl} | **{c_count}** | {b_str} |")

    return {
        "success": True,
        "active_count": active_count,
        "total_count": total_count,
        "inactive_count": inactive_count,
        "class_breakdown": list(class_breakdown),
        "kpis": kpis,
        "markdown": "\n".join(md),
        "student_ids": list(qs.filter(is_active=True).values_list('id', flat=True))
    }


def get_admitted_students(period='this_month', month=None, year=None):
    """
    Returns students admitted in a given period or calendar month.
    """
    today = timezone.now().date()
    qs = Student.objects.all().select_related('user')

    if month and year:
        target_year, target_month = int(year), int(month)
        qs = qs.filter(admission_date__year=target_year, admission_date__month=target_month)
        period_title = f"{date(target_year, target_month, 1).strftime('%B %Y')}"
    elif period == 'last_month':
        first_of_this_month = today.replace(day=1)
        last_month_end = first_of_this_month - timedelta(days=1)
        target_year, target_month = last_month_end.year, last_month_end.month
        qs = qs.filter(admission_date__year=target_year, admission_date__month=target_month)
        period_title = f"Last Month ({date(target_year, target_month, 1).strftime('%B %Y')})"
    else:  # this_month
        target_year, target_month = today.year, today.month
        qs = qs.filter(admission_date__year=target_year, admission_date__month=target_month)
        period_title = f"This Month ({today.strftime('%B %Y')})"

    count = qs.count()

    # If count is 0 for current month, also report latest admission date recorded
    latest_student = Student.objects.order_by('-admission_date').first()
    latest_str = f"Latest recorded admission in system: {latest_student.admission_date.strftime('%d %b %Y')}" if latest_student else ""

    md = [
        f"### 📅 Student Admissions ({period_title})",
        f"- **Admissions Recorded in {period_title}:** **{count} student(s)**"
    ]
    if count == 0 and latest_str:
        md.append(f"- *Note:* {latest_str}")

    if count > 0:
        md.append("")
        md.append("| Student Name | Student ID | Class | Parent Name | Parent Mobile | Admission Date | Action |")
        md.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
        for s in qs[:25]:
            profile_url = f"/dashboard/students/{s.id}/"
            md.append(f"| **{s.user.get_full_name()}** | `{s.student_id}` | Class {s.current_class} ({s.board}) | {s.parent_name} | {s.parent_phone} | {s.admission_date.strftime('%d %b %Y')} | [View Profile]({profile_url}) |")

    return {
        "success": True,
        "count": count,
        "period": period_title,
        "student_ids": list(qs.values_list('id', flat=True)),
        "markdown": "\n".join(md)
    }


def find_students(query):
    """
    Searches for students by full or partial name, student_id, phone, or parent name.
    Handles duplicate and multiple matches clearly.
    """
    clean_query = query.strip()
    if not clean_query:
        return {"success": False, "error": "Search query cannot be empty."}

    # Match across multiple fields
    q_filter = (
        Q(user__first_name__icontains=clean_query) |
        Q(user__last_name__icontains=clean_query) |
        Q(user__username__icontains=clean_query) |
        Q(student_id__icontains=clean_query) |
        Q(parent_name__icontains=clean_query) |
        Q(parent_phone__icontains=clean_query)
    )

    matches = list(Student.objects.filter(q_filter).select_related('user'))

    if not matches:
        # Also try split parts
        parts = clean_query.split()
        if len(parts) > 1:
            q_split = Q(user__first_name__icontains=parts[0]) & Q(user__last_name__icontains=parts[1])
            matches = list(Student.objects.filter(q_split).select_related('user'))

    return {
        "success": True,
        "count": len(matches),
        "matches": matches
    }


# ==============================================================================
# 2. FEE MANAGEMENT TOOLS
# ==============================================================================

def get_pending_fees_list(class_level=None, min_amount=None, overdue_days=None, student_ids=None, limit=50):
    """
    Retrieves all students with pending or partial fees, calculating exact outstanding balance.
    """
    payments_qs = Payment.objects.filter(status__in=['pending', 'partial']).select_related('student__user', 'batch')

    if class_level:
        payments_qs = payments_qs.filter(student__current_class=str(class_level))

    if student_ids:
        payments_qs = payments_qs.filter(student_id__in=student_ids)

    if overdue_days is not None:
        cutoff_date = timezone.now().date() - timedelta(days=int(overdue_days))
        payments_qs = payments_qs.filter(month__lte=cutoff_date)

    # Group dues per student
    student_dues = {}
    for p in payments_qs:
        sid = p.student_id
        bal = p.amount_due - p.amount_paid
        if bal <= 0:
            continue
        if sid not in student_dues:
            student_dues[sid] = {
                "student": p.student,
                "total_due": Decimal('0.00'),
                "total_paid": Decimal('0.00'),
                "total_amount": Decimal('0.00'),
                "pending_records": 0,
                "months": []
            }
        student_dues[sid]["total_due"] += bal
        student_dues[sid]["total_paid"] += p.amount_paid
        student_dues[sid]["total_amount"] += p.amount_due
        student_dues[sid]["pending_records"] += 1
        student_dues[sid]["months"].append(p.month.strftime("%b %Y"))

    # Apply min_amount filter if provided
    if min_amount is not None:
        min_dec = Decimal(str(min_amount))
        student_dues = {sid: data for sid, data in student_dues.items() if data["total_due"] >= min_dec}

    # Sort students by total_due descending
    sorted_students = sorted(student_dues.values(), key=lambda x: x["total_due"], reverse=True)

    total_pending_amount = sum(x["total_due"] for x in sorted_students)
    student_count = len(sorted_students)

    # Format Markdown
    title_suffix = ""
    if class_level:
        title_suffix += f" for Class {class_level}"
    if min_amount:
        title_suffix += f" (Above {format_currency(min_amount)})"
    if overdue_days:
        title_suffix += f" (Overdue > {overdue_days} Days)"

    kpis = [
        {"label": "Total Pending Dues", "value": format_currency(total_pending_amount), "color": "rose"},
        {"label": "Students with Dues", "value": str(student_count), "color": "amber"},
        {"label": "Average Pending / Student", "value": format_currency(total_pending_amount / (student_count or 1)), "color": "blue"},
    ]

    md = [
        f"### 💳 Outstanding Fees Report{title_suffix}",
        f"- **Total Outstanding Amount:** **{format_currency(total_pending_amount)}**",
        f"- **Students with Dues:** **{student_count}** student(s)",
        ""
    ]

    if student_count == 0:
        md.append("✅ **No pending dues found matching the specified criteria!**")
    else:
        md.append("| Student Name | Class | Parent Name | Parent Mobile | Total Fee | Paid | Outstanding Due | Action |")
        md.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")

        for item in sorted_students[:limit]:
            s = item["student"]
            profile_url = f"/dashboard/students/{s.id}/"
            name = s.user.get_full_name() or s.user.username
            md.append(
                f"| **{name}** (`{s.student_id}`) | Class {s.current_class} {s.board} | "
                f"{s.parent_name} | `{s.parent_phone}` | "
                f"{format_currency(item['total_amount'])} | {format_currency(item['total_paid'])} | "
                f"**{format_currency(item['total_due'])}** | [View Profile]({profile_url}) |"
            )

        if student_count > limit:
            md.append(f"\n*Showing top {limit} of {student_count} students with outstanding fees.*")

    return {
        "success": True,
        "student_count": student_count,
        "total_pending_amount": float(total_pending_amount),
        "kpis": kpis,
        "markdown": "\n".join(md),
        "student_ids": [x["student"].id for x in sorted_students]
    }


def get_fee_collection_stats(period='this_month', month=None, year=None):
    """
    Returns collected fees summary for a specific calendar month or all time.
    """
    today = timezone.now().date()
    qs = PaymentTransaction.objects.all()

    # Overall all-time collection
    all_time_total = qs.aggregate(s=Sum('amount'))['s'] or Decimal('0.00')
    all_time_count = qs.count()

    if month and year:
        target_year, target_month = int(year), int(month)
        qs_period = qs.filter(payment_date__year=target_year, payment_date__month=target_month)
        p_name = date(target_year, target_month, 1).strftime('%B %Y')
    elif period == 'last_month':
        first_of_this_month = today.replace(day=1)
        last_month_end = first_of_this_month - timedelta(days=1)
        target_year, target_month = last_month_end.year, last_month_end.month
        qs_period = qs.filter(payment_date__year=target_year, payment_date__month=target_month)
        p_name = date(target_year, target_month, 1).strftime('%B %Y')
    elif period == 'all_time':
        qs_period = qs
        p_name = "All Time"
    else:  # this_month
        target_year, target_month = today.year, today.month
        qs_period = qs.filter(payment_date__year=target_year, payment_date__month=target_month)
        p_name = today.strftime('%B %Y')

    period_total = qs_period.aggregate(s=Sum('amount'))['s'] or Decimal('0.00')
    period_tx_count = qs_period.count()

    # Breakdown by payment mode for this period
    modes = qs_period.values('payment_mode').annotate(total=Sum('amount'), count=Count('id')).order_by('-total')

    # Latest recorded transactions in database if current period is empty
    latest_tx = PaymentTransaction.objects.order_by('-payment_date').first()

    kpis = [
        {"label": f"Collected in {p_name}", "value": format_currency(period_total), "color": "emerald"},
        {"label": "Transactions", "value": str(period_tx_count), "color": "blue"},
        {"label": "All-Time Collected", "value": format_currency(all_time_total), "color": "purple"},
    ]

    md = [
        f"### 💰 Fee Collection Summary ({p_name})",
        f"- **Total Collected in {p_name}:** **{format_currency(period_total)}** across **{period_tx_count}** transaction(s)",
        f"- **All-Time Institute Collections:** **{format_currency(all_time_total)}** ({all_time_count} transactions recorded)"
    ]

    if period_total == 0 and latest_tx:
        md.append(f"- *Note:* No transactions recorded in {p_name} yet. Latest recorded transaction date: **{latest_tx.payment_date.strftime('%d %B %Y')}** (₹{latest_tx.amount}).")

    if modes:
        md.append("")
        md.append("#### **Payment Mode Breakdown:**")
        md.append("| Mode | Total Amount | Transactions |")
        md.append("| :--- | :---: | :---: |")
        for m in modes:
            md.append(f"| {m['payment_mode'].upper()} | **{format_currency(m['total'])}** | {m['count']} |")

    return {
        "success": True,
        "period": p_name,
        "period_total": float(period_total),
        "all_time_total": float(all_time_total),
        "kpis": kpis,
        "markdown": "\n".join(md)
    }


def get_pending_fees_by_class():
    """
    Ranks classes by highest outstanding fees.
    """
    class_dues = Payment.objects.filter(
        status__in=['pending', 'partial']
    ).values('student__current_class').annotate(
        total_pending=Sum(F('amount_due') - F('amount_paid')),
        pending_students=Count('student', distinct=True)
    ).order_by('-total_pending')

    total_pending = sum(c['total_pending'] for c in class_dues)

    md = [
        "### 📊 Classes Ranked by Highest Pending Fees",
        f"- **Combined Institute Pending Dues:** **{format_currency(total_pending)}**",
        "",
        "| Rank | Class | Total Outstanding Due | Affected Students | % of Total Dues |",
        "| :---: | :--- | :---: | :---: | :---: |"
    ]

    for idx, c in enumerate(class_dues, start=1):
        cls_name = f"Class {c['student__current_class']}"
        amt = c['total_pending']
        pct = (amt / total_pending * 100) if total_pending else 0
        md.append(f"| #{idx} | **{cls_name}** | **{format_currency(amt)}** | {c['pending_students']} students | {pct:.1f}% |")

    return {
        "success": True,
        "total_pending": float(total_pending),
        "rankings": list(class_dues),
        "markdown": "\n".join(md)
    }


def get_student_fee_status(student):
    """
    Detailed fee status and payment history for a specific student.
    """
    payments = Payment.objects.filter(student=student).select_related('batch').order_by('month')

    total_due = sum(p.amount_due for p in payments)
    total_paid = sum(p.amount_paid for p in payments)
    balance = total_due - total_paid

    pending_payments = [p for p in payments if p.status in ['pending', 'partial']]

    profile_url = f"/dashboard/students/{student.id}/"
    collect_url = f"/dashboard/payments/collect/"

    status_tag = "✅ ALL FEES PAID" if balance <= 0 else f"⚠️ PENDING: {format_currency(balance)}"

    md = [
        f"### 📋 Fee Status: {student.user.get_full_name()} (`{student.student_id}`)",
        f"- **Class & Board:** Class {student.current_class} ({student.board}) | **School:** {student.school_name or 'N/A'}",
        f"- **Parent Name:** {student.parent_name} | **Mobile:** `{student.parent_phone}`",
        f"- **Overall Fee Status:** **{status_tag}**",
        f"- **Total Fees Billed:** {format_currency(total_due)} | **Total Paid:** {format_currency(total_paid)} | **Balance Due:** **{format_currency(balance)}**",
        f"- [Open Student Profile]({profile_url}) &nbsp;|&nbsp; [Collect Fee]({collect_url})",
        "",
        "#### **Month-by-Month Fee Register:**",
        "| Month | Batch | Billed | Paid | Due | Status | Mode / Receipt |",
        "| :--- | :--- | :--- | :--- | :--- | :---: | :--- |"
    ]

    for p in payments:
        p_due = p.amount_due - p.amount_paid
        badge = "🟢 Paid" if p.status == 'paid' else ("🟡 Partial" if p.status == 'partial' else "🔴 Pending")
        rcpt = p.receipt_number or (p.payment_mode or "-")
        md.append(
            f"| {p.month.strftime('%B %Y')} | {p.batch.batch_name} | "
            f"{format_currency(p.amount_due)} | {format_currency(p.amount_paid)} | "
            f"{format_currency(p_due)} | {badge} | {rcpt} |"
        )

    return {
        "success": True,
        "student": student,
        "total_due": float(total_due),
        "total_paid": float(total_paid),
        "balance": float(balance),
        "has_dues": balance > 0,
        "markdown": "\n".join(md)
    }


def get_parent_contact_details(student):
    """
    Returns registered contact details for a student's parent/guardian.
    """
    # Also check if other students share the same parent phone
    siblings = Student.objects.filter(parent_phone=student.parent_phone).exclude(id=student.id).select_related('user')

    profile_url = f"/dashboard/students/{student.id}/"

    md = [
        f"### 📞 Parent Contact Information",
        f"- **Student:** **{student.user.get_full_name()}** (ID: `{student.student_id}`, Class {student.current_class} {student.board})",
        f"- **Parent / Guardian Name:** **{student.parent_name}**",
        f"- **Registered Mobile Number:** **[{student.parent_phone}](tel:{student.parent_phone})**",
        f"- **Parent Email:** {student.parent_email or 'Not provided'}",
        f"- **Residential Address:** {student.address or 'Not provided'}",
        f"- [View Complete Student Profile]({profile_url})"
    ]

    if siblings.exists():
        md.append("")
        md.append("#### **Other Enrolled Students with Same Parent Contact (Siblings):**")
        for sib in siblings:
            md.append(f"- **{sib.user.get_full_name()}** (Class {sib.current_class} {sib.board}, ID: `{sib.student_id}`) - [Profile](/dashboard/students/{sib.id}/)")

    return {
        "success": True,
        "student_name": student.user.get_full_name(),
        "parent_name": student.parent_name,
        "parent_phone": student.parent_phone,
        "parent_email": student.parent_email,
        "markdown": "\n".join(md)
    }


# ==============================================================================
# 3. ATTENDANCE & ACADEMIC TOOLS
# ==============================================================================

def get_attendance_overview(date_val=None):
    """
    Returns attendance summary for a given date (defaults to today or latest session).
    """
    today = timezone.now().date()
    target_date = date_val or today

    sessions = AttendanceSession.objects.filter(date=target_date).select_related('batch')
    session_count = sessions.count()

    # If 0 on today, check latest recorded attendance session date
    latest_session = AttendanceSession.objects.order_by('-date').first()

    records = AttendanceRecord.objects.filter(session__date=target_date)
    total_records = records.count()
    present_count = records.filter(status='present').count()
    absent_count = records.filter(status='absent').count()
    late_count = records.filter(status='late').count()

    rate = (present_count / total_records * 100) if total_records > 0 else 0

    date_str = target_date.strftime('%A, %d %B %Y')

    kpis = [
        {"label": "Sessions Marked", "value": str(session_count), "color": "blue"},
        {"label": "Present Students", "value": str(present_count), "color": "emerald"},
        {"label": "Absentees", "value": str(absent_count), "color": "rose"},
        {"label": "Attendance Rate", "value": f"{rate:.1f}%", "color": "teal"}
    ]

    md = [
        f"### 📅 Attendance Summary: {date_str}",
        f"- **Batches with Roll Call Marked:** **{session_count}**",
        f"- **Present:** **{present_count}** &bull; **Absent:** **{absent_count}** &bull; **Late:** **{late_count}**",
        f"- **Overall Attendance Rate:** **{rate:.1f}%**"
    ]

    if total_records == 0 and latest_session:
        md.append(f"- *Note:* No attendance was marked on {date_str}. Latest recorded roll call session was on **{latest_session.date.strftime('%d %B %Y')}** for batch *{latest_session.batch.batch_name}*.")

    if absent_count > 0:
        md.append("")
        md.append("#### **Absentees List:**")
        md.append("| Student Name | Class | Batch | Parent Contact |")
        md.append("| :--- | :--- | :--- | :--- |")
        for r in records.filter(status='absent').select_related('student__user', 'session__batch'):
            st = r.student
            md.append(f"| **{st.user.get_full_name()}** | Class {st.current_class} | {r.session.batch.batch_name} | {st.parent_name} (`{st.parent_phone}`) |")

    return {
        "success": True,
        "date": str(target_date),
        "total": total_records,
        "present": present_count,
        "absent": absent_count,
        "rate": rate,
        "kpis": kpis,
        "markdown": "\n".join(md)
    }


def get_batches_and_classes_summary(class_level=None):
    """
    Returns list of active batches, teachers, strength, and schedule.
    """
    qs = Batch.objects.filter(is_active=True).select_related('teacher__user').prefetch_related('subjects', 'students')

    if class_level:
        qs = qs.filter(class_level=str(class_level))

    count = qs.count()
    total_capacity = sum(b.max_students for b in qs)

    md = [
        f"### 🏫 Academic Batches & Classes Summary",
        f"- **Active Batches:** **{count}**",
        f"- **Total Student Capacity:** **{total_capacity}** seats",
        "",
        "| Batch Name | Class & Board | Assigned Faculty | Days & Timing | Strength | Fee/Month |",
        "| :--- | :--- | :--- | :--- | :---: | :---: |"
    ]

    for b in qs[:30]:
        teacher_name = b.teacher.user.get_full_name() if b.teacher else "Unassigned"
        strength = f"{b.current_strength}/{b.max_students}"
        timing = f"{b.get_days_display()} ({b.start_time.strftime('%I:%M %p')} - {b.end_time.strftime('%I:%M %p')})"
        md.append(f"| **{b.batch_name}** (`{b.batch_code}`) | Class {b.class_level} {b.board} | {teacher_name} | {timing} | **{strength}** | {format_currency(b.monthly_fee)} |")

    return {
        "success": True,
        "batch_count": count,
        "markdown": "\n".join(md)
    }


def get_staff_overview():
    """
    Returns staff directory, active faculty, and salaries summary.
    """
    staff_qs = Staff.objects.all().select_related('user')
    total = staff_qs.count()
    active = staff_qs.filter(is_active=True).count()
    total_salary = staff_qs.aggregate(s=Sum('salary'))['s'] or Decimal('0.00')

    md = [
        f"### 👥 Faculty & Staff Directory",
        f"- **Total Staff Members:** **{total}** (Active: **{active}**)",
        f"- **Monthly Payroll Expense:** **{format_currency(total_salary)}**",
        "",
        "| Name | Designation | Subject Expertise | Phone | Monthly Salary | Status |",
        "| :--- | :--- | :--- | :--- | :---: | :---: |"
    ]

    for st in staff_qs:
        name = st.user.get_full_name() or st.user.username
        phone = st.user.phone or "N/A"
        status = "Active" if st.is_active else "Inactive"
        md.append(f"| **{name}** | {st.designation} | {st.subject_expertise or '-'} | {phone} | {format_currency(st.salary)} | {status} |")

    return {
        "success": True,
        "total": total,
        "active": active,
        "total_salary": float(total_salary),
        "markdown": "\n".join(md)
    }


def get_inquiries_overview():
    """
    Returns status of prospective student admissions inquiries and leads.
    """
    qs = Inquiry.objects.all().order_by('-submitted_at')
    total = qs.count()
    pending = qs.filter(is_followed_up=False).count()

    md = [
        f"### 📩 Admission Inquiries & Leads",
        f"- **Total Inquiries:** **{total}**",
        f"- **Pending Follow-up:** **{pending}** lead(s)",
        ""
    ]

    if total > 0:
        md.append("| Candidate Name | Interested Class | Phone | Email | Submitted Date | Status |")
        md.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
        for inq in qs[:15]:
            status_badge = "✅ Followed up" if inq.is_followed_up else "🔴 Pending Follow-up"
            md.append(f"| **{inq.name}** | {inq.interested_class} | {inq.phone} | {inq.email or '-'} | {inq.submitted_at.strftime('%d %b %Y')} | {status_badge} |")

    return {
        "success": True,
        "total": total,
        "pending": pending,
        "markdown": "\n".join(md)
    }
