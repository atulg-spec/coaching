from django import forms
from .models import ChatbotConfig


class ChatbotConfigForm(forms.ModelForm):
    api_token = forms.CharField(
        required=False,
        widget=forms.PasswordInput(
            render_value=True,
            attrs={
                'class': 'w-full px-4 py-2.5 rounded-lg border border-slate-300 focus:ring-2 focus:ring-secondary focus:border-secondary text-sm transition',
                'placeholder': 'Enter Cloudflare API Token (Workers AI permission)'
            }
        ),
        help_text="Your token remains securely stored in the platform database."
    )

    class Meta:
        model = ChatbotConfig
        fields = [
            'account_id',
            'api_token',
            'model_name',
            'system_prompt',
            'temperature',
            'max_tokens',
            'is_active',
            'enable_for_students',
            'enable_for_staff',
            'enable_public_widget',
        ]
        widgets = {
            'account_id': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 rounded-lg border border-slate-300 focus:ring-2 focus:ring-secondary focus:border-secondary text-sm transition font-mono',
                'placeholder': 'e.g. 8a3f4e912b7c6d5e4f3a2b1c0d9e8f7a'
            }),
            'model_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 rounded-lg border border-slate-300 focus:ring-2 focus:ring-secondary focus:border-secondary text-sm transition font-mono',
                'placeholder': '@cf/meta/llama-3.1-8b-instruct'
            }),
            'system_prompt': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 rounded-lg border border-slate-300 focus:ring-2 focus:ring-secondary focus:border-secondary text-sm transition',
                'rows': 5,
                'placeholder': 'Define the AI persona and instructions for tutoring, tone, and guidance...'
            }),
            'temperature': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 rounded-lg border border-slate-300 focus:ring-2 focus:ring-secondary focus:border-secondary text-sm transition',
                'step': '0.05',
                'min': '0.0',
                'max': '1.0'
            }),
            'max_tokens': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 rounded-lg border border-slate-300 focus:ring-2 focus:ring-secondary focus:border-secondary text-sm transition',
                'step': '64',
                'min': '128',
                'max': '4096'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-secondary rounded border-slate-300 focus:ring-secondary'
            }),
            'enable_for_students': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-secondary rounded border-slate-300 focus:ring-secondary'
            }),
            'enable_for_staff': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-secondary rounded border-slate-300 focus:ring-secondary'
            }),
            'enable_public_widget': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-secondary rounded border-slate-300 focus:ring-secondary'
            }),
        }
