from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Payment, PaymentTransaction, Inquiry
from students.models import Student
from accounts.decorators import admin_required


from decimal import Decimal
from django.utils import timezone

import decimal

@admin_required
def collect_fee(request):
    if request.method == 'POST':
        student_id = request.POST.get('student_id')
        try:
            amount_val = request.POST.get('amount_paid')
            if not amount_val:
                raise ValueError
            amount_paid = Decimal(amount_val)
            if amount_paid <= 0:
                raise ValueError
        except (ValueError, TypeError, decimal.InvalidOperation):
            messages.error(request, "Invalid amount. Please enter a positive number.")
            return redirect('collect_fee')
            
        payment_mode = request.POST.get('payment_mode')
        
        # Always ensure the current month's dues are generated for all active batches
        student = get_object_or_404(Student, id=student_id)
        first_day = timezone.now().date().replace(day=1)
        for batch in student.batches.filter(is_active=True):
            Payment.objects.get_or_create(
                student=student,
                batch=batch,
                month=first_day,
                defaults={
                    'amount_due': batch.monthly_fee,
                    'status': 'pending'
                }
            )
            
        pending_payments = list(Payment.objects.filter(
            student=student, 
            status__in=['pending', 'partial']
        ).order_by('month'))
        
        if not pending_payments:
            messages.error(request, "This student has no pending dues to pay.")
            return redirect('collect_fee')
                
        total_balance = sum((p.amount_due - p.amount_paid) for p in pending_payments)
        if amount_paid > total_balance:
            messages.error(request, f"Amount paid (₹{amount_paid}) exceeds the total pending dues (₹{total_balance}). Cannot accept overpayments.")
            return redirect('collect_fee')
            
        remaining_amount = amount_paid
        payments_updated = 0
        
        for payment in pending_payments:
            if remaining_amount <= 0:
                break
                
            balance = payment.amount_due - payment.amount_paid
            if balance <= 0:
                continue
                
            if remaining_amount >= balance:
                allocated = balance
                payment.amount_paid += balance
                payment.status = 'paid'
                remaining_amount -= balance
            else:
                allocated = remaining_amount
                payment.amount_paid += remaining_amount
                payment.status = 'partial'
                remaining_amount = Decimal('0.00')
                
            payment.payment_mode = payment_mode
            payment.payment_date = timezone.now().date()
            payment.collected_by = request.user
            if not payment.receipt_number:
                payment.receipt_number = f"REC-{timezone.now().strftime('%Y%m%d%H%M%S')}-{payment.id}"
            payment.save()
            
            if allocated > 0:
                # Create the actual transaction record
                tx = PaymentTransaction.objects.create(
                    payment=payment,
                    amount=allocated,
                    payment_mode=payment_mode,
                    receipt_number=f"TXN-{timezone.now().strftime('%Y%m%d%H%M%S')}-{payment.id}",
                    collected_by=request.user
                )
                
                if not getattr(request, '_tx_ids', None):
                    request._tx_ids = []
                request._tx_ids.append(str(tx.id))
                
                payments_updated += 1
            
        if remaining_amount > 0:
            messages.warning(request, f"Fee of ₹{amount_paid - remaining_amount} allocated. ₹{remaining_amount} was left over (exceeds pending dues).")
        else:
            messages.success(request, f"Fee of ₹{amount_paid} collected successfully and applied to {payments_updated} record(s).")
            
        if getattr(request, '_tx_ids', None):
            request.session['open_receipt_ids'] = ",".join(request._tx_ids)
            
        return redirect('collect_fee')
        
    open_receipt_ids = request.session.pop('open_receipt_ids', None)
    students = Student.objects.filter(is_active=True)
    return render(request, 'dashboard/payments/collect.html', {'students': students, 'open_receipt_ids': open_receipt_ids})


@admin_required
def dues_report(request):
    pending_payments = Payment.objects.filter(status='pending').select_related('student__user', 'batch')
    return render(request, 'dashboard/payments/dues.html', {'pending_payments': pending_payments})


@admin_required
def payment_history(request):
    transactions = PaymentTransaction.objects.all().order_by('-payment_date').select_related('payment__student__user', 'payment__batch')
    return render(request, 'dashboard/payments/history.html', {'transactions': transactions})


@admin_required
def receipt(request, pk):
    transaction = get_object_or_404(PaymentTransaction, pk=pk)
    return render(request, 'dashboard/payments/receipt.html', {'transaction': transaction})

@admin_required
def combined_receipt(request):
    tx_ids = request.GET.get('tx_ids', '')
    if not tx_ids:
        return redirect('payment_history')
    
    ids = [int(i) for i in tx_ids.split(',') if i.isdigit()]
    transactions = PaymentTransaction.objects.filter(id__in=ids)
    
    if not transactions:
        return redirect('payment_history')
        
    first_tx = transactions.first()
    total_amount = sum(tx.amount for tx in transactions)
    distinct_months = sorted(list(set(tx.payment.month for tx in transactions)))
    fee_months = ", ".join(m.strftime("%B %Y") for m in distinct_months)
    
    context = {
        'transactions': transactions,
        'first_tx': first_tx,
        'total_amount': total_amount,
        'fee_months': fee_months,
        'receipt_number': first_tx.receipt_number + (f" (+{len(transactions)-1} more)" if len(transactions) > 1 else "")
    }
    return render(request, 'dashboard/payments/combined_receipt.html', context)


@admin_required
def inquiry_list(request):
    inquiries = Inquiry.objects.all().order_by('-submitted_at')
    return render(request, 'dashboard/inquiries/list.html', {'inquiries': inquiries})

@admin_required
def pay_staff_salary(request):
    from staff.models import Staff
    from .models import StaffSalary
    import calendar
    import datetime

    staff_members = Staff.objects.filter(is_active=True)
    today = timezone.now().date()
    
    # Default to current month
    default_month_str = today.strftime('%Y-%m')
    month_str = request.GET.get('month', default_month_str)
    
    try:
        year, month = map(int, month_str.split('-'))
        selected_month = datetime.date(year, month, 1)
    except ValueError:
        selected_month = today.replace(day=1)

    if request.method == 'POST':
        staff_id = request.POST.get('staff_id')
        try:
            amount_paid = Decimal(request.POST.get('amount_paid'))
            if amount_paid <= 0:
                raise ValueError
        except (ValueError, TypeError, decimal.InvalidOperation):
            messages.error(request, "Invalid amount.")
            return redirect(f"{request.path}?month={month_str}")

        payment_mode = request.POST.get('payment_mode')
        remarks = request.POST.get('remarks', '')

        staff = get_object_or_404(Staff, id=staff_id)

        salary, created = StaffSalary.objects.get_or_create(
            staff=staff,
            month=selected_month,
            defaults={
                'amount_paid': amount_paid,
                'status': 'paid',
                'payment_mode': payment_mode,
                'payment_date': today,
                'processed_by': request.user,
                'remarks': remarks
            }
        )
        if not created:
            salary.amount_paid += amount_paid
            salary.status = 'paid'
            salary.payment_mode = payment_mode
            salary.payment_date = today
            salary.processed_by = request.user
            if remarks:
                salary.remarks += f"\n{remarks}"
            salary.save()

        messages.success(request, f"Salary payment of ₹{amount_paid} recorded for {staff.user.get_full_name()}.")
        return redirect(f"{request.path}?month={month_str}")

    # Prepare data for all staff for the selected month
    staff_data = []
    salaries = {s.staff_id: s for s in StaffSalary.objects.filter(month=selected_month)}
    
    for staff in staff_members:
        salary_record = salaries.get(staff.id)
        staff_data.append({
            'staff': staff,
            'salary_record': salary_record,
        })

    return render(request, 'dashboard/payments/staff_salary.html', {
        'staff_members': staff_members,
        'staff_data': staff_data,
        'selected_month': selected_month,
        'month_str': month_str,
    })

@admin_required
def staff_salary_history(request):
    from .models import StaffSalary
    salaries = StaffSalary.objects.select_related('staff__user', 'processed_by').order_by('-month', '-payment_date')
    return render(request, 'dashboard/payments/staff_salary_history.html', {'salaries': salaries})
