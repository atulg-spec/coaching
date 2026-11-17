from core.models import Notice

def dashboard_base(request):
    context = {}
    if not request.user.is_authenticated:
        context['base_template'] = 'base_dashboard.html'
        return context

    if request.user.role == 'staff':
        context['base_template'] = 'base_staff.html'
        context['active_notices'] = Notice.objects.filter(is_active=True)
    elif request.user.role == 'student':
        context['base_template'] = 'base_dashboard.html'
        context['active_notices'] = Notice.objects.filter(is_active=True, target_audience='all')
    else:
        # Admin
        context['base_template'] = 'base_dashboard.html'
        context['active_notices'] = Notice.objects.filter(is_active=True)

    return context
