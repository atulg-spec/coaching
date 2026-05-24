from django.contrib import admin
from django.utils.html import format_html
from django.utils.timezone import localtime

from .models import (
    AttendanceSession,
    AttendanceRecord,
    StaffAttendance,
)


# =========================
# INLINE ADMIN
# =========================

class AttendanceRecordInline(admin.TabularInline):
    model = AttendanceRecord
    extra = 0
    autocomplete_fields = ['student']
    fields = ('student', 'status', 'remarks')
    show_change_link = True


# =========================
# ATTENDANCE SESSION ADMIN
# =========================

@admin.register(AttendanceSession)
class AttendanceSessionAdmin(admin.ModelAdmin):
    list_display = (
        'batch',
        'formatted_date',
        'attendance_summary',
        'marked_by',
        'formatted_marked_at',
    )

    list_filter = (
        'batch',
        'date',
        'marked_by',
    )

    search_fields = (
        'batch__name',
        'topic_covered',
    )

    autocomplete_fields = (
        'batch',
        'marked_by',
    )

    readonly_fields = (
        'marked_at',
        'present_count',
        'absent_count',
        'late_count',
        'leave_count',
    )

    ordering = ('-date', '-marked_at')
    date_hierarchy = 'date'

    inlines = [AttendanceRecordInline]

    list_per_page = 25
    save_on_top = True

    fieldsets = (
        ('Session Information', {
            'fields': (
                ('batch', 'date'),
                'topic_covered',
            )
        }),

        ('Attendance Summary', {
            'fields': (
                ('present_count', 'absent_count'),
                ('late_count', 'leave_count'),
            )
        }),

        ('Tracking Information', {
            'classes': ('collapse',),
            'fields': (
                'marked_by',
                'marked_at',
            )
        }),
    )

    # -------------------------
    # CUSTOM METHODS
    # -------------------------

    def formatted_date(self, obj):
        return obj.date.strftime("%d %b %Y")
    formatted_date.short_description = "Date"

    def formatted_marked_at(self, obj):
        return localtime(obj.marked_at).strftime("%d %b %Y • %I:%M %p")
    formatted_marked_at.short_description = "Marked At"

    def present_count(self, obj):
        return obj.records.filter(status='present').count()
    present_count.short_description = "Present Students"

    def absent_count(self, obj):
        return obj.records.filter(status='absent').count()
    absent_count.short_description = "Absent Students"

    def late_count(self, obj):
        return obj.records.filter(status='late').count()
    late_count.short_description = "Late Students"

    def leave_count(self, obj):
        return obj.records.filter(status='leave').count()
    leave_count.short_description = "Leave Students"

    def attendance_summary(self, obj):
        present = obj.records.filter(status='present').count()
        absent = obj.records.filter(status='absent').count()
        late = obj.records.filter(status='late').count()

        return format_html(
            '''
            <div style="display:flex;gap:6px;flex-wrap:wrap;">
                <span style="background:#dcfce7;color:#166534;
                padding:3px 10px;border-radius:20px;font-size:12px;font-weight:600;">
                ✓ {}
                </span>

                <span style="background:#fee2e2;color:#991b1b;
                padding:3px 10px;border-radius:20px;font-size:12px;font-weight:600;">
                ✗ {}
                </span>

                <span style="background:#fef3c7;color:#92400e;
                padding:3px 10px;border-radius:20px;font-size:12px;font-weight:600;">
                ⏰ {}
                </span>
            </div>
            ''',
            present,
            absent,
            late,
        )

    attendance_summary.short_description = "Attendance"


# =========================
# ATTENDANCE RECORD ADMIN
# =========================

@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = (
        'student',
        'session',
        'colored_status',
        'remarks',
    )

    list_filter = (
        'status',
        'session__batch',
        'session__date',
    )

    search_fields = (
        'student__name',
        'remarks',
    )

    autocomplete_fields = (
        'student',
        'session',
    )

    ordering = ('-session__date',)

    list_per_page = 30

    fieldsets = (
        ('Attendance Record', {
            'fields': (
                'session',
                'student',
                'status',
                'remarks',
            )
        }),
    )

    actions = [
        'mark_present',
        'mark_absent',
        'mark_leave',
    ]

    # -------------------------
    # STATUS BADGE
    # -------------------------

    def colored_status(self, obj):
        colors = {
            'present': '#16a34a',
            'absent': '#dc2626',
            'late': '#d97706',
            'leave': '#2563eb',
        }

        icons = {
            'present': '✓',
            'absent': '✗',
            'late': '⏰',
            'leave': '☾',
        }

        color = colors.get(obj.status, '#6b7280')
        icon = icons.get(obj.status, '•')

        return format_html(
            '<span style="padding:4px 12px;border-radius:20px;'
            'background:{}20;color:{};font-weight:600;">{} {}</span>',
            color,
            color,
            icon,
            obj.get_status_display()
        )

    colored_status.short_description = "Status"

    # -------------------------
    # ACTIONS
    # -------------------------

    @admin.action(description="Mark selected students as PRESENT")
    def mark_present(self, request, queryset):
        queryset.update(status='present')

    @admin.action(description="Mark selected students as ABSENT")
    def mark_absent(self, request, queryset):
        queryset.update(status='absent')

    @admin.action(description="Mark selected students as ON LEAVE")
    def mark_leave(self, request, queryset):
        queryset.update(status='leave')


# =========================
# STAFF ATTENDANCE ADMIN
# =========================

@admin.register(StaffAttendance)
class StaffAttendanceAdmin(admin.ModelAdmin):
    list_display = (
        'staff',
        'formatted_date',
        'colored_status',
        'in_time',
        'out_time',
        'working_hours',
        'marked_by',
    )

    list_filter = (
        'status',
        'date',
        'marked_by',
    )

    search_fields = (
        'staff__name',
    )

    autocomplete_fields = (
        'staff',
        'marked_by',
    )

    ordering = ('-date',)
    date_hierarchy = 'date'

    list_per_page = 25
    save_on_top = True

    fieldsets = (
        ('Staff Information', {
            'fields': (
                'staff',
                'date',
            )
        }),

        ('Attendance Details', {
            'fields': (
                'status',
                ('in_time', 'out_time'),
            )
        }),

        ('Tracking', {
            'classes': ('collapse',),
            'fields': (
                'marked_by',
            )
        }),
    )

    actions = [
        'mark_staff_present',
        'mark_staff_absent',
        'mark_half_day',
    ]

    # -------------------------
    # CUSTOM METHODS
    # -------------------------

    def formatted_date(self, obj):
        return obj.date.strftime("%d %b %Y")
    formatted_date.short_description = "Date"

    def colored_status(self, obj):
        colors = {
            'present': '#16a34a',
            'absent': '#dc2626',
            'half_day': '#d97706',
            'leave': '#2563eb',
        }

        color = colors.get(obj.status, '#6b7280')

        return format_html(
            '<span style="padding:4px 12px;border-radius:20px;'
            'background:{}20;color:{};font-weight:600;">{}</span>',
            color,
            color,
            obj.get_status_display()
        )

    colored_status.short_description = "Status"

    def working_hours(self, obj):
        if obj.in_time and obj.out_time:
            return f"{obj.in_time} → {obj.out_time}"
        return "-"

    working_hours.short_description = "Working Hours"

    # -------------------------
    # ACTIONS
    # -------------------------

    @admin.action(description="Mark selected staff as PRESENT")
    def mark_staff_present(self, request, queryset):
        queryset.update(status='present')

    @admin.action(description="Mark selected staff as ABSENT")
    def mark_staff_absent(self, request, queryset):
        queryset.update(status='absent')

    @admin.action(description="Mark selected staff as HALF DAY")
    def mark_half_day(self, request, queryset):
        queryset.update(status='half_day')