from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def admin_required(view_func):
    """
    Decorator that checks if the user is authenticated and is an admin.
    Redirects to dashboard login if not authenticated or not an admin.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, "Please login to access the dashboard.")
            return redirect('dashboard:login')

        if not request.user.is_admin:
            messages.error(request, "You do not have permission to access the admin dashboard.")
            return redirect('dashboard:login')

        return view_func(request, *args, **kwargs)
    return wrapper
