from django.db import models
from django.conf import settings


class ChatbotConfig(models.Model):
    MODEL_CHOICES = [
        ('@cf/meta/llama-3.1-8b-instruct', 'Meta Llama 3.1 8B Instruct (Recommended)'),
        ('@cf/meta/llama-3-8b-instruct', 'Meta Llama 3 8B Instruct'),
        ('@cf/meta/llama-3.2-3b-instruct', 'Meta Llama 3.2 3B Instruct (Fast)'),
        ('@cf/meta/llama-3.2-1b-instruct', 'Meta Llama 3.2 1B Instruct (Ultra Fast)'),
        ('@cf/mistral/mistral-7b-instruct-v0.1', 'Mistral 7B Instruct v0.1'),
        ('@cf/qwen/qwen1.5-7b-chat-awq', 'Qwen 1.5 7B Chat'),
        ('@cf/deepseek-ai/deepseek-math-7b-instruct', 'DeepSeek Math 7B Instruct'),
    ]

    account_id = models.CharField(
        max_length=120,
        blank=True,
        verbose_name="Cloudflare Account ID",
        help_text="Your Cloudflare Account ID from the Cloudflare Dashboard overview."
    )
    api_token = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Cloudflare API Token",
        help_text="API Token with 'Workers AI: Read' or 'Workers AI: Edit' permissions."
    )
    model_name = models.CharField(
        max_length=150,
        default='@cf/meta/llama-3.1-8b-instruct',
        verbose_name="AI Model",
        help_text="Model tag to run on Cloudflare Workers AI (e.g., @cf/meta/llama-3.1-8b-instruct)"
    )
    system_prompt = models.TextField(
        default=(
            "You are Natasha, an intelligent personal assistant for the coaching institute administrator at Success Coaching. "
            "You have full contextual understanding of the institute's ERP database including student profiles, fee registers, "
            "collections, pending dues, parent contacts, batch timetables, and attendance records. "
            "Provide accurate, professional, data-backed answers with structured summaries, KPI metrics, and tables."
        ),
        verbose_name="System Persona / Prompt",
        help_text="Instructions defining how the AI chatbot should respond."
    )
    temperature = models.FloatField(
        default=0.7,
        help_text="Randomness/creativity (0.0 to 1.0). Default is 0.7."
    )
    max_tokens = models.PositiveIntegerField(
        default=1024,
        help_text="Maximum tokens to generate per response (e.g. 512, 1024, 2048)."
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Chatbot Enabled",
        help_text="Global switch to enable or disable the AI chatbot."
    )
    enable_for_students = models.BooleanField(
        default=True,
        verbose_name="Enable for Students",
        help_text="Allow students to access the AI tutor from the student portal."
    )
    enable_for_staff = models.BooleanField(
        default=True,
        verbose_name="Enable for Staff & Admin",
        help_text="Allow staff and teachers to access the chatbot in the dashboard."
    )
    enable_public_widget = models.BooleanField(
        default=True,
        verbose_name="Enable Public Widget",
        help_text="Show interactive floating assistant on public coaching website."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cloudflare Chatbot Setting"
        verbose_name_plural = "Cloudflare Chatbot Settings"

    def __str__(self):
        status = "Active" if self.is_active else "Disabled"
        return f"Chatbot Configuration ({self.model_name}) - {status}"

    @property
    def is_configured(self):
        return bool(self.account_id and self.account_id.strip() and self.api_token and self.api_token.strip())

    @classmethod
    def get_settings(cls):
        """Retrieve active configuration or create default placeholder."""
        config = cls.objects.first()
        if not config:
            config = cls.objects.create()
        return config


class ChatConversation(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='chat_conversations'
    )
    session_key = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    title = models.CharField(max_length=255, default='New Chat')
    context_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = "Chat Conversation"
        verbose_name_plural = "Chat Conversations"

    def __str__(self):
        user_display = self.user.username if self.user else f"Guest ({self.session_key[:8] if self.session_key else 'anon'})"
        return f"{self.title} - {user_display}"


class ChatMessage(models.Model):
    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
        ('system', 'System'),
    ]

    conversation = models.ForeignKey(
        ChatConversation,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = "Chat Message"
        verbose_name_plural = "Chat Messages"

    def __str__(self):
        preview = (self.content[:40] + '...') if len(self.content) > 40 else self.content
        return f"[{self.role}] {preview}"
