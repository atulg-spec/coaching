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
