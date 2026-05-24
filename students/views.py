from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q
from django.contrib.auth import get_user_model
from .models import Student
from .forms import StudentForm
from batches.models import Batch
from accounts.decorators import admin_required, staff_or_admin_required

User = get_user_model()


@staff_or_admin_required
def student_list(request):
    user = request.user
    query = request.GET.get('q', '')

    if user.role == 'admin':
        students = Student.objects.all()
    else:
        # Staff: only students in their batches
        try:
            my_batches = user.staff.batch_set.all()
            students = Student.objects.filter(batches__in=my_batches).distinct()
        except Exception:
            students = Student.objects.none()

    if query:
        students = students.filter(
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(student_id__icontains=query)
        )
    return render(request, 'dashboard/students/list.html', {
        'students': students, 'query': query,
        'readonly': user.role == 'staff',
    })


@staff_or_admin_required
def student_detail(request, pk):
    student = get_object_or_404(Student, pk=pk)
    return render(request, 'dashboard/students/detail.html', {
        'student': student,
        'readonly': request.user.role == 'staff',
    })


@admin_required
def student_add(request):
    if request.method == 'POST':
        form = StudentForm(request.POST, request.FILES)
        if form.is_valid():
            first_name = form.cleaned_data['first_name']
            last_name = form.cleaned_data.get('last_name', '')
            user = User.objects.create_user(
                username=(first_name + last_name).lower() or 'student',
                first_name=first_name,
                last_name=last_name,
                email=form.cleaned_data['email'],
                role='student'
            )
            password = form.cleaned_data.get('password') or 'success123'
            user.set_password(password)
            user.save()
            student = form.save(commit=False)
            student.user = user
            student.student_id = f"SCC202500{Student.objects.count()+1}"
            student.save()
            
            # Handle batch assignment from the form
            batch_ids = request.POST.getlist('batches')
            if batch_ids:
                for batch_id in batch_ids:
                    try:
                        batch = Batch.objects.get(id=batch_id)
                        batch.students.add(student)
                    except Batch.DoesNotExist:
                        pass
                        
            messages.success(request, f"Student {student.user.get_full_name()} added successfully.")
            return redirect('student_detail', pk=student.id)
    else:
        form = StudentForm()
    
    active_batches = Batch.objects.filter(is_active=True).order_by('class_level', 'batch_name')
    return render(request, 'dashboard/students/form.html', {
        'form': form, 
        'title': 'Add Student',
        'active_batches': active_batches
    })


@admin_required
def student_edit(request, pk):
    student = get_object_or_404(Student, pk=pk)
    if request.method == 'POST':
        form = StudentForm(request.POST, request.FILES, instance=student)
        if form.is_valid():
            form.save()
            student.user.first_name = form.cleaned_data['first_name']
            student.user.last_name = form.cleaned_data['last_name']
            student.user.email = form.cleaned_data['email']
            password = form.cleaned_data.get('password')
            if password:
                student.user.set_password(password)
            student.user.save()
            
            # Handle batch assignment updates
            batch_ids = request.POST.getlist('batches')
            if batch_ids is not None and 'batches' in request.POST:
                student.batches.clear()
                for batch_id in batch_ids:
                    try:
                        batch = Batch.objects.get(id=batch_id)
                        batch.students.add(student)
                    except Batch.DoesNotExist:
                        pass
            
            messages.success(request, "Student updated successfully.")
            return redirect('student_detail', pk=student.pk)
    else:
        form = StudentForm(instance=student, initial={
            'first_name': student.user.first_name,
            'last_name': student.user.last_name,
            'email': student.user.email,
        })
        
    active_batches = Batch.objects.filter(is_active=True).order_by('class_level', 'batch_name')
    return render(request, 'dashboard/students/form.html', {
        'form': form, 
        'title': 'Edit Student',
        'active_batches': active_batches,
        'student': student
    })
