from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def admin_required(view_func):
    """Only users with role='admin' can access."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if request.user.role != 'admin':
            messages.error(request, "You don't have permission to access this page.")
            return redirect('role_redirect')
        return view_func(request, *args, **kwargs)
    return wrapper


def staff_or_admin_required(view_func):
    """Users with role='admin' or role='staff' can access."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if request.user.role not in ('admin', 'staff'):
            messages.error(request, "Access denied.")
            return redirect('role_redirect')
        return view_func(request, *args, **kwargs)
    return wrapper


def student_required(view_func):
    """Only users with role='student' can access."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if request.user.role != 'student':
            return redirect('role_redirect')
        return view_func(request, *args, **kwargs)
    return wrapper
