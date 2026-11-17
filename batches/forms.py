from django import forms
from .models import Batch, Subject

class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['name', 'code']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all',
                'placeholder': 'Enter subject name (e.g., Mathematics, Physics, English)'
            }),
            'code': forms.TextInput(attrs={
                'class': 'w-full border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all',
                'placeholder': 'Enter subject code (e.g., MATH101, PHY202, ENG101)'
            }),
        }
        labels = {
            'name': 'Subject Name',
            'code': 'Subject Code',
        }
        help_texts = {
            'name': 'The full name of the subject (e.g., "Advanced Mathematics")',
            'code': 'A unique identifier or course code (e.g., "MATH301")',
        }
        error_messages = {
            'name': {
                'required': 'Please enter the subject name.',
                'max_length': 'Subject name cannot exceed 200 characters.',
            },
            'code': {
                'required': 'Please enter the subject code.',
                'unique': 'This subject code already exists. Please use a unique code.',
                'max_length': 'Subject code cannot exceed 20 characters.',
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add additional styling or attributes if needed
        for field_name, field in self.fields.items():
            if field.required:
                field.widget.attrs['required'] = 'required'

class BatchForm(forms.ModelForm):
    class Meta:
        model = Batch
        fields = ['batch_name', 'batch_code', 'class_level', 'board', 'subjects', 'teacher', 'days', 'time_slot', 'start_time', 'end_time', 'start_date', 'max_students', 'room_number', 'monthly_fee']
        widgets = {
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'subjects': forms.CheckboxSelectMultiple(),
        }

from .models import StudyMaterial

class StudyMaterialForm(forms.ModelForm):
    class Meta:
        model = StudyMaterial
        fields = ['title', 'description', 'file']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all',
                'placeholder': 'Enter study material title (e.g., Physics Chapter 1 Notes)'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all',
                'rows': 3,
                'placeholder': 'Enter a short description about the study material...'
            }),
            'file': forms.FileInput(attrs={
                'class': 'w-full border border-gray-300 rounded px-3 py-2 text-gray-500 focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all cursor-pointer file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-primary/10 file:text-primary hover:file:bg-primary/20'
            })
        }

        labels = {
            'title': 'Study Material Title',
            'description': 'Description',
            'file': 'Upload File',
        }

        help_texts = {
            'title': 'Enter the name of the study material.',
            'description': 'Optional short description for students.',
            'file': 'Upload PDF, DOCX, images, or other supported files.',
        }

        error_messages = {
            'title': {
                'required': 'Please enter the study material title.',
                'max_length': 'Title cannot exceed the allowed character limit.',
            },
            'file': {
                'required': 'Please upload a study material file.',
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Add required attribute to required fields
        for field_name, field in self.fields.items():
            if field.required:
                field.widget.attrs['required'] = 'required'