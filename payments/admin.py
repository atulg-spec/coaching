from django.contrib import admin
from django.db.models import Sum
from django.utils.html import format_html
from django.utils.timezone import now

from .models import (
    FeeStructure,
    Payment,
    PaymentTransaction,
    Inquiry,
    StaffSalary,
)


# =========================
# INLINE ADMIN
# =========================

class PaymentTransactionInline(admin.TabularInline):
    model = PaymentTransaction
    extra = 0
    autocomplete_fields = ['collected_by']
    readonly_fields = ['payment_date']
    classes = ['collapse']


# =========================
# FEE STRUCTURE ADMIN
# =========================

@admin.register(FeeStructure)
class FeeStructureAdmin(admin.ModelAdmin):
    list_display = (
        'batch',
        'monthly_fee',
        'registration_fee',
        'effective_from',
    )

    list_filter = ('effective_from', 'batch')
    search_fields = ('batch__name',)
    date_hierarchy = 'effective_from'
    ordering = ('-effective_from',)

    fieldsets = (
        ('Batch Information', {
            'fields': ('batch',)
        }),
        ('Fee Details', {
            'fields': (
                'monthly_fee',
                'registration_fee',
                'effective_from',
            )
        }),
    )


# =========================
# PAYMENT ADMIN
# =========================

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'student',
        'batch',
        'formatted_month',
        'amount_due',
        'amount_paid',
        'colored_balance',
        'colored_status',
        'payment_mode',
        'payment_date',
    )

    list_filter = (
        'status',
        'payment_mode',
        'batch',
        'month',
        'payment_date',
    )

    search_fields = (
        'student__name',
        'student__phone',
        'receipt_number',
        'remarks',
    )

    autocomplete_fields = (
        'student',
        'batch',
        'collected_by',
    )

    readonly_fields = (
        'balance_display',
    )

    ordering = ('-month', '-payment_date')
    date_hierarchy = 'payment_date'

    inlines = [PaymentTransactionInline]

    list_per_page = 25
    save_on_top = True

    fieldsets = (
        ('Student Information', {
            'fields': (
                'student',
                'batch',
                'month',
            )
        }),

        ('Payment Details', {
            'fields': (
                ('amount_due', 'amount_paid'),
                'balance_display',
                ('status', 'payment_mode'),
            )
        }),

        ('Receipt & Collection', {
            'fields': (
                ('receipt_number', 'payment_date'),
                'collected_by',
            )
        }),

        ('Additional Information', {
            'classes': ('collapse',),
            'fields': ('remarks',)
        }),
    )

    actions = [
        'mark_as_paid',
        'mark_as_pending',
        'mark_as_waived',
    ]

    # -------------------------
    # CUSTOM METHODS
    # -------------------------

    def formatted_month(self, obj):
        return obj.month.strftime("%b %Y")
    formatted_month.short_description = "Month"

    def colored_status(self, obj):
        colors = {
            'paid': '#16a34a',
            'pending': '#dc2626',
            'partial': '#d97706',
            'waived': '#2563eb',
        }

        return format_html(
            '<span style="padding:4px 10px;border-radius:20px;'
            'background:{}20;color:{};font-weight:600;">{}</span>',
            colors.get(obj.status, '#6b7280'),
            colors.get(obj.status, '#6b7280'),
            obj.get_status_display()
        )

    colored_status.short_description = "Status"

    def colored_balance(self, obj):
        balance = obj.balance_due

        color = '#16a34a' if balance <= 0 else '#dc2626'

        return format_html(
            '<strong style="color:{};">₹ {}</strong>',
            color,
            balance
        )

    colored_balance.short_description = "Balance"

    def balance_display(self, obj):
        if obj.pk:
            return format_html(
                '<strong style="font-size:15px;">₹ {}</strong>',
                obj.balance_due
            )
        return "₹ 0"

    balance_display.short_description = "Remaining Balance"

    # -------------------------
    # ACTIONS
    # -------------------------

    @admin.action(description="Mark selected payments as PAID")
    def mark_as_paid(self, request, queryset):
        queryset.update(
            status='paid',
            payment_date=now().date()
        )

    @admin.action(description="Mark selected payments as PENDING")
    def mark_as_pending(self, request, queryset):
        queryset.update(status='pending')

    @admin.action(description="Mark selected payments as WAIVED")
    def mark_as_waived(self, request, queryset):
        queryset.update(status='waived')


# =========================
# PAYMENT TRANSACTION ADMIN
# =========================

@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = (
        'receipt_number',
        'payment',
        'amount',
        'payment_mode',
        'payment_date',
        'collected_by',
    )

    list_filter = (
        'payment_mode',
        'payment_date',
    )

    search_fields = (
        'receipt_number',
        'payment__student__name',
    )

    autocomplete_fields = (
        'payment',
        'collected_by',
    )

    readonly_fields = ('payment_date',)

    ordering = ('-payment_date',)
    date_hierarchy = 'payment_date'


# =========================
# INQUIRY ADMIN
# =========================

@admin.register(Inquiry)
class InquiryAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'phone',
        'email',
        'interested_class',
        'follow_up_status',
        'submitted_at',
    )

    list_filter = (
        'is_followed_up',
        'interested_class',
        'submitted_at',
    )

    search_fields = (
        'name',
        'phone',
        'email',
        'message',
    )

    readonly_fields = ('submitted_at',)

    ordering = ('-submitted_at',)
    date_hierarchy = 'submitted_at'

    actions = ['mark_followed_up']

    fieldsets = (
        ('Student Inquiry', {
            'fields': (
                ('name', 'phone'),
                'email',
                'interested_class',
            )
        }),

        ('Message', {
            'fields': ('message',)
        }),

        ('Follow Up', {
            'fields': (
                'is_followed_up',
                'submitted_at',
            )
        }),
    )

    def follow_up_status(self, obj):
        if obj.is_followed_up:
            return format_html(
                '<span style="color:#16a34a;font-weight:600;">{}</span>',
                '✓ Followed Up'
            )

        return format_html(
            '<span style="color:#dc2626;font-weight:600;">{}</span>',
            '✗ Pending'
        )

    follow_up_status.short_description = "Status"

    @admin.action(description="Mark selected inquiries as followed up")
    def mark_followed_up(self, request, queryset):
        queryset.update(is_followed_up=True)


# =========================
# STAFF SALARY ADMIN
# =========================

@admin.register(StaffSalary)
class StaffSalaryAdmin(admin.ModelAdmin):
    list_display = (
        'staff',
        'formatted_month',
        'amount_paid',
        'colored_status',
        'payment_mode',
        'payment_date',
        'processed_by',
    )

    list_filter = (
        'status',
        'payment_mode',
        'month',
        'payment_date',
    )

    search_fields = (
        'staff__name',
        'remarks',
    )

    autocomplete_fields = (
        'staff',
        'processed_by',
    )

    ordering = ('-month',)
    date_hierarchy = 'payment_date'

    fieldsets = (
        ('Staff Details', {
            'fields': (
                'staff',
                'month',
            )
        }),

        ('Salary Payment', {
            'fields': (
                'amount_paid',
                ('status', 'payment_mode'),
                'payment_date',
            )
        }),

        ('Processing Details', {
            'fields': (
                'processed_by',
                'remarks',
            )
        }),
    )

    actions = [
        'mark_salary_paid',
        'mark_salary_pending',
    ]

    def formatted_month(self, obj):
        return obj.month.strftime("%b %Y")
    formatted_month.short_description = "Salary Month"

    def colored_status(self, obj):
        color = '#16a34a' if obj.status == 'paid' else '#dc2626'

        return format_html(
            '<span style="padding:4px 10px;border-radius:20px;'
            'background:{}20;color:{};font-weight:600;">{}</span>',
            color,
            color,
            obj.get_status_display()
        )

    colored_status.short_description = "Status"

    @admin.action(description="Mark selected salaries as PAID")
    def mark_salary_paid(self, request, queryset):
        queryset.update(
            status='paid',
            payment_date=now().date()
        )

    @admin.action(description="Mark selected salaries as PENDING")
    def mark_salary_pending(self, request, queryset):
        queryset.update(status='pending')