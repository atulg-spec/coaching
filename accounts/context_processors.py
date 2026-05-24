def dashboard_base(request):
    if not request.user.is_authenticated:
        return {'base_template': 'base_dashboard.html'}
    if request.user.role == 'staff':
        return {'base_template': 'base_staff.html'}
    return {'base_template': 'base_dashboard.html'}
