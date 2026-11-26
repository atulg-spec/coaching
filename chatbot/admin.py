from django.contrib import admin, messages
from django.utils.html import format_html
from django.urls import reverse
from .models import ChatbotConfig, ChatConversation, ChatMessage
from .services import CloudflareAIService


@admin.register(ChatbotConfig)
class ChatbotConfigAdmin(admin.ModelAdmin):
    list_display = (
        'model_name',
        'account_id_masked',
        'is_active_badge',
        'students_badge',
        'staff_badge',
        'updated_at',
    )
    readonly_fields = ('updated_at', 'created_at', 'connection_tester_html')
    fieldsets = (
        ('Cloudflare API Credentials', {
            'description': (
                'Configure your Cloudflare Workers AI credentials. '
                'Find your <strong>Account ID</strong> on the Cloudflare Dashboard overview right sidebar. '
                'Create an <strong>API Token</strong> under User Profile &rarr; API Tokens with <em>Workers AI: Edit</em> or <em>Workers AI: Read</em> permissions.'
            ),
            'fields': (
                'account_id',
                'api_token',
                'connection_tester_html',
            )
        }),
        ('AI Model & Prompt Configuration', {
            'fields': (
                'model_name',
                'system_prompt',
                'temperature',
                'max_tokens',
            )
        }),
        ('Feature Switches & Access Control', {
            'fields': (
                'is_active',
                'enable_for_students',
                'enable_for_staff',
                'enable_public_widget',
            )
        }),
        ('Audit Metadata', {
            'classes': ('collapse',),
            'fields': ('created_at', 'updated_at'),
        }),
    )

    actions = ['test_cloudflare_connection_action']

    def account_id_masked(self, obj):
        if not obj.account_id:
            return format_html('<span style="color:#e53e3e;font-weight:bold;">Not Configured</span>')
        masked = obj.account_id[:4] + '••••' + obj.account_id[-4:] if len(obj.account_id) > 8 else '••••••••'
        return format_html('<code>{}</code>', masked)
    account_id_masked.short_description = "Account ID"

    def is_active_badge(self, obj):
        if obj.is_active:
            return format_html('<span style="background:#38a169;color:#fff;padding:2px 8px;border-radius:9999px;font-size:11px;font-weight:bold;">Active</span>')
        return format_html('<span style="background:#e53e3e;color:#fff;padding:2px 8px;border-radius:9999px;font-size:11px;font-weight:bold;">Disabled</span>')
    is_active_badge.short_description = "Status"

    def students_badge(self, obj):
        return "✅ Yes" if obj.enable_for_students else "❌ No"
    students_badge.short_description = "Students"

    def staff_badge(self, obj):
        return "✅ Yes" if obj.enable_for_staff else "❌ No"
    staff_badge.short_description = "Staff"

    def connection_tester_html(self, obj):
        dashboard_settings_url = reverse('chatbot_settings')
        if obj.is_configured:
            return format_html(
                '<div style="padding:10px 14px;background:#f0fff4;border:1px solid #c6f6d5;border-radius:8px;color:#22543d;">'
                'Credentials entered. You can test live from the <strong><a href="{}" target="_blank" style="color:#2b6cb0;text-decoration:underline;">Admin Dashboard Settings Panel &rarr;</a></strong> or save and run the admin action.'
                '</div>',
                dashboard_settings_url
            )
        return format_html(
            '<div style="padding:10px 14px;background:#fffaf0;border:1px solid #feebc8;border-radius:8px;color:#744210;">'
            'Please fill in your Cloudflare Account ID and API Token above and click Save.'
            '</div>'
        )
    connection_tester_html.short_description = "Connection Status"

    def test_cloudflare_connection_action(self, request, queryset):
        for config in queryset:
            res = CloudflareAIService.test_connection(config.account_id, config.api_token, config.model_name)
            if res.get('success'):
                self.message_user(
                    request,
                    f"Success! Cloudflare AI connection verified for model {config.model_name}. Sample reply: '{res.get('sample_reply', '')}'",
                    level=messages.SUCCESS
                )
            else:
                self.message_user(
                    request,
                    f"Cloudflare Connection Failed: {res.get('error')}",
                    level=messages.ERROR
                )
    test_cloudflare_connection_action.short_description = "Test Cloudflare API Connection"

    def has_add_permission(self, request):
        # Enforce singleton pattern in admin: only allow 1 config row
        if ChatbotConfig.objects.exists():
            return False
        return super().has_add_permission(request)


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    readonly_fields = ('role', 'content', 'created_at')
    can_delete = True


@admin.register(ChatConversation)
class ChatConversationAdmin(admin.ModelAdmin):
    list_display = ('title', 'user_display', 'message_count', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('title', 'user__username', 'user__first_name', 'user__last_name', 'session_key')
    inlines = [ChatMessageInline]

    def user_display(self, obj):
        if obj.user:
            return f"{obj.user.get_full_name() or obj.user.username} ({obj.user.role})"
        return f"Visitor ({obj.session_key[:8] if obj.session_key else 'anon'})"
    user_display.short_description = "User"

    def message_count(self, obj):
        return obj.messages.count()
    message_count.short_description = "Messages"


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('conversation', 'role', 'content_preview', 'created_at')
    list_filter = ('role', 'created_at')
    search_fields = ('content', 'conversation__title', 'conversation__user__username')

    def content_preview(self, obj):
        return (obj.content[:60] + '...') if len(obj.content) > 60 else obj.content
    content_preview.short_description = "Content"
