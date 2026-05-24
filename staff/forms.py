from django import forms
from .models import Staff

class StaffForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, label='First Name')
    last_name  = forms.CharField(max_length=150, label='Last Name', required=False)
    email      = forms.EmailField(required=False, label='Email Address')
    phone      = forms.CharField(max_length=15, required=False, label='Phone Number')
    password   = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Leave blank to use default (staff123)'}), required=False, label='Password', help_text='Set a custom password or leave blank for default.')

    class Meta:
        model = Staff
        fields = [
            'employee_id', 'designation', 'subject_expertise',
            'qualification', 'date_of_joining', 'salary',
            'address', 'emergency_contact',
        ]
        labels = {
            'employee_id':        'Employee ID',
            'designation':        'Designation',
            'subject_expertise':  'Subject(s) Taught',
            'qualification':      'Qualification',
            'date_of_joining':    'Date of Joining',
            'salary':             'Monthly Salary (₹)',
            'address':            'Residential Address',
            'emergency_contact':  'Emergency Contact No.',
        }
        widgets = {
            'date_of_joining': forms.DateInput(attrs={'type': 'date'}),
            'address':         forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        field_order = ['first_name', 'last_name', 'email', 'phone'] + [
            f for f in self.fields if f not in ('first_name', 'last_name', 'email', 'phone')
        ]
        self.fields = {k: self.fields[k] for k in field_order}
