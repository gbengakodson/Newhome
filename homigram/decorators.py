# core/decorators.py
# core/decorators.py
from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps


def tenant_required(view_func):
    """Decorator to check if user is a tenant"""

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')

        if request.user.profile.user_type != 'tenant':
            messages.error(request, 'This section is for tenants only.')
            return redirect('home')

        return view_func(request, *args, **kwargs)

    return _wrapped_view


def landlord_required(view_func):
    """Decorator to check if user is a landlord"""

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')

        if request.user.profile.user_type != 'landlord':
            messages.error(request, 'This section is for landlords only.')
            return redirect('home')

        return view_func(request, *args, **kwargs)

    return _wrapped_view


def verified_required(view_func):
    """Decorator to check if user is verified"""

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')

        if not request.user.profile.is_verified:
            messages.warning(request, 'You need to verify your account to access this page.')
            return redirect('submit_verification')

        return view_func(request, *args, **kwargs)

    return _wrapped_view


def tenant_verified_required(view_func):
    """Decorator to check if user is a verified tenant"""

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')

        if request.user.profile.user_type != 'tenant':
            messages.error(request, 'This section is for tenants only.')
            return redirect('home')

        if not request.user.profile.is_verified:
            messages.warning(request, 'Your tenant account must be verified to access this page.')
            return redirect('submit_verification')

        return view_func(request, *args, **kwargs)

    return _wrapped_view


# In decorators.py
def landlord_verified_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')

        if request.user.profile.user_type != 'landlord':
            messages.error(request, 'This section is for landlords only.')
            return redirect('home')

        if not request.user.profile.is_verified:
            messages.warning(request, 'Your landlord account must be verified to post properties.')
            return redirect('submit_verification')

        return view_func(request, *args, **kwargs)

    return _wrapped_view


from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def verified_and_funded_required(view_func):
    """Decorator to check if user is verified and has sufficient balance"""

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')

        # Check email verification
        if not request.user.profile.email_verified:
            messages.warning(request, 'Please verify your email address first.')
            return redirect('home')

        # Check identity verification
        if not request.user.profile.is_verified:
            messages.warning(request, 'You need to verify your account before inspecting properties.')
            return redirect('submit_verification')

        # Get property and check balance
        property_id = kwargs.get('property_id')
        if property_id:
            from .models import Property
            property = Property.objects.get(id=property_id)
            if request.user.profile.wallet_balance < property.inspection_fee:
                messages.error(request, f'Insufficient balance. You need ₦{property.inspection_fee}')
                return redirect('fund_wallet')

        return view_func(request, *args, **kwargs)

    return _wrapped_view