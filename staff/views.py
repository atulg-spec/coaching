from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q
from django.contrib.auth import get_user_model
from .models import Staff
from .forms import StaffForm
from accounts.decorators import admin_required

User = get_user_model()


@admin_required
def staff_list(request):
    query = request.GET.get('q', '')
    staff_members = Staff.objects.all()
    if query:
        staff_members = staff_members.filter(
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(employee_id__icontains=query) |
            Q(designation__icontains=query)
        )
    return render(request, 'dashboard/staff/list.html', {'staff_members': staff_members, 'query': query})


@admin_required
def staff_detail(request, pk):
    staff = get_object_or_404(Staff, pk=pk)
    
    from attendance.models import StaffAttendance
    attendance_qs = StaffAttendance.objects.filter(staff=staff)
    
    total_days = attendance_qs.count()
    present_days = attendance_qs.filter(status='present').count()
    absent_days = attendance_qs.filter(status='absent').count()
    half_days = attendance_qs.filter(status='half_day').count()
    leave_days = attendance_qs.filter(status='leave').count()
    
    # Calculate percentage: Present + Half Day (as 0.5) / Total Days
    if total_days > 0:
        effective_present = present_days + (half_days * 0.5)
        attendance_percentage = round((effective_present / total_days) * 100, 1)
    else:
        attendance_percentage = 0
        
    attendance_stats = {
        'total': total_days,
        'present': present_days,
        'absent': absent_days,
        'half_day': half_days,
        'leave': leave_days,
        'percentage': attendance_percentage
    }
    
    attendance_records = attendance_qs.order_by('-date')[:30]
    
    from payments.models import StaffSalary
    salary_records = StaffSalary.objects.filter(staff=staff).order_by('-payment_date')[:12]
    
    return render(request, 'dashboard/staff/detail.html', {
        'staff': staff,
        'attendance_stats': attendance_stats,
        'attendance_records': attendance_records,
        'salary_records': salary_records,
    })


@admin_required
def staff_add(request):
    if request.method == 'POST':
        form = StaffForm(request.POST)
        if form.is_valid():
            user = User.objects.create_user(
                username=form.cleaned_data['first_name'].lower() + form.cleaned_data.get('last_name', '').lower() + str(Staff.objects.count()),
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data.get('last_name', ''),
                email=form.cleaned_data['email'],
                role='staff'
            )
            password = form.cleaned_data.get('password') or 'staff123'
            user.set_password(password)
            user.save()
            staff = form.save(commit=False)
            staff.user = user
            staff.save()
            messages.success(request, "Staff member added successfully.")
            return redirect('staff_list')
    else:
        form = StaffForm()
    return render(request, 'dashboard/staff/form.html', {'form': form, 'title': 'Add Staff Member'})


@admin_required
def staff_edit(request, pk):
    staff = get_object_or_404(Staff, pk=pk)
    if request.method == 'POST':
        form = StaffForm(request.POST, instance=staff)
        if form.is_valid():
            form.save()
            staff.user.first_name = form.cleaned_data['first_name']
            staff.user.last_name = form.cleaned_data.get('last_name', '')
            staff.user.email = form.cleaned_data['email']
            password = form.cleaned_data.get('password')
            if password:
                staff.user.set_password(password)
            staff.user.save()
            messages.success(request, "Staff member updated successfully.")
            return redirect('staff_detail', pk=staff.pk)
    else:
        form = StaffForm(instance=staff, initial={
            'first_name': staff.user.first_name,
            'last_name': staff.user.last_name,
            'email': staff.user.email,
        })
    return render(request, 'dashboard/staff/form.html', {'form': form, 'title': 'Edit Staff Member'})
