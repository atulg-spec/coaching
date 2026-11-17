from django import forms
from .models import Notice

class NoticeForm(forms.ModelForm):
    class Meta:
        model = Notice
        fields = ['title', 'content', 'target_audience', 'is_active']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 4}),
        }
