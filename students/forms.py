from django import forms
from .models import Student

class StudentForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, label='First Name')
    last_name  = forms.CharField(max_length=150, label='Last Name', required=False)
    email      = forms.EmailField(required=False, label='Student Email')
    password   = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Leave blank to use default (success123)'}), required=False, label='Password', help_text='Set a custom password or leave blank for default.')

    class Meta:
        model = Student
        fields = [
            'date_of_birth', 'board', 'current_class',
            'school_name', 'parent_name', 'parent_phone', 'parent_email',
            'address', 'photo',
        ]
        labels = {
            'date_of_birth':  'Date of Birth',
            'board':          'Board',
            'current_class':  'Class',
            'school_name':    'School Name',
            'parent_name':    'Parent / Guardian Name',
            'parent_phone':   'Parent Phone',
            'parent_email':   'Parent Email',
            'address':        'Home Address',
            'photo':          'Student Photo',
        }
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'address':       forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Put user fields first
        field_order = ['first_name', 'last_name', 'email'] + [
            f for f in self.fields if f not in ('first_name', 'last_name', 'email')
        ]
        self.fields = {k: self.fields[k] for k in field_order}
