from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Batch, Subject
from .forms import BatchForm, SubjectForm
from accounts.decorators import admin_required, staff_or_admin_required
from students.models import Student


@staff_or_admin_required
def batch_list(request):
    user = request.user
    if user.role == 'admin':
        batches = Batch.objects.all()
    else:
        try:
            batches = Batch.objects.filter(teacher=user.staff)
        except Exception:
            batches = Batch.objects.none()
    return render(request, 'dashboard/batches/list.html', {
        'batches': batches,
        'readonly': user.role == 'staff',
    })


@staff_or_admin_required
def batch_detail(request, pk):
    batch = get_object_or_404(Batch, pk=pk)
    
    already_in_batch = batch.students.values_list('id', flat=True)
    available_students = Student.objects.filter(
        is_active=True,
        current_class=batch.class_level,
    ).exclude(id__in=already_in_batch).select_related('user')
    
    return render(request, 'dashboard/batches/detail.html', {
        'batch': batch,
        'available_students': available_students,
        'readonly': request.user.role == 'staff',
    })


@admin_required
def batch_add(request):
    if request.method == 'POST':
        form = BatchForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Batch created successfully.")
            return redirect('batch_list')
    else:
        form = BatchForm()
    return render(request, 'dashboard/batches/form.html', {'form': form, 'title': 'Create Batch'})


@admin_required
def batch_edit(request, pk):
    batch = get_object_or_404(Batch, pk=pk)
    if request.method == 'POST':
        form = BatchForm(request.POST, instance=batch)
        if form.is_valid():
            form.save()
            messages.success(request, "Batch updated successfully.")
            return redirect('batch_detail', pk=batch.pk)
    else:
        form = BatchForm(instance=batch)
    return render(request, 'dashboard/batches/form.html', {'form': form, 'title': 'Edit Batch'})

@admin_required
def batch_add_student(request, batch_id):
    batch = get_object_or_404(Batch, id=batch_id)
    
    if request.method == 'POST':
        student_id = request.POST.get('student_id')
        if not student_id:
            messages.error(request, "No student selected.")
            return redirect('batch_detail', pk=batch_id)
        
        student = get_object_or_404(Student, id=student_id)
        
        if student in batch.students.all():
            messages.warning(request, f"{student.user.get_full_name()} is already in this batch.")
        else:
            batch.students.add(student)
            messages.success(request, f"{student.user.get_full_name()} added to {batch.batch_name} successfully.")
        
        return redirect('batch_detail', pk=batch_id)
    
    # GET shouldn't be hit directly if using modal, but fallback to detail page
    return redirect('batch_detail', pk=batch_id)


@admin_required
def batch_remove_student(request, batch_id, student_id):
    batch = get_object_or_404(Batch, id=batch_id)
    student = get_object_or_404(Student, id=student_id)
    
    if request.method == 'POST':
        batch.students.remove(student)
        messages.success(request, f"{student.user.get_full_name()} removed from {batch.batch_name}.")
    
    return redirect('batch_detail', pk=batch_id)

@admin_required
def subject_list(request):
    subjects = Subject.objects.all()
    return render(request, 'dashboard/batches/subject_list.html', {'subjects': subjects})

@admin_required
def subject_add(request):
    if request.method == 'POST':
        form = SubjectForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Subject created successfully.")
            return redirect('subject_list')
    else:
        form = SubjectForm()
    return render(request, 'dashboard/batches/subject_form.html', {'form': form, 'title': 'Add Subject'})

@admin_required
def subject_edit(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    if request.method == 'POST':
        form = SubjectForm(request.POST, instance=subject)
        if form.is_valid():
            form.save()
            messages.success(request, "Subject updated successfully.")
            return redirect('subject_list')
    else:
        form = SubjectForm(instance=subject)
    return render(request, 'dashboard/batches/subject_form.html', {'form': form, 'title': 'Edit Subject'})

from .models import StudyMaterial
from .forms import StudyMaterialForm

@staff_or_admin_required
def upload_material(request, batch_id):
    batch = get_object_or_404(Batch, id=batch_id)
    if request.user.role != 'admin' and batch.teacher != request.user.staff:
        messages.error(request, "You are not authorized to upload material for this batch.")
        return redirect('batch_detail', pk=batch_id)
        
    if request.method == 'POST':
        form = StudyMaterialForm(request.POST, request.FILES)
        if form.is_valid():
            material = form.save(commit=False)
            material.batch = batch
            material.uploaded_by = request.user
            material.save()
            messages.success(request, "Study material uploaded successfully.")
            return redirect('batch_detail', pk=batch_id)
    else:
        form = StudyMaterialForm()
        
    return render(request, 'dashboard/batches/upload_material.html', {
        'form': form,
        'batch': batch
    })

@staff_or_admin_required
def delete_material(request, material_id):
    material = get_object_or_404(StudyMaterial, id=material_id)
    batch_id = material.batch.id
    if request.user.role == 'admin' or material.batch.teacher == request.user.staff:
        material.file.delete()
        material.delete()
        messages.success(request, "Material deleted.")
    else:
        messages.error(request, "Not authorized to delete this material.")
    return redirect('batch_detail', pk=batch_id)
