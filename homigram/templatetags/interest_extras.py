# core/templatetags/interest_extras.py
# core/templatetags/interest_extras.py
from django import template
from datetime import timedelta
from homigram.models import SignedAgreement, Interest

register = template.Library()

@register.filter
def add_days(value, days):
    """Add days to a datetime object"""
    if value is None:
        return None
    return value + timedelta(days=int(days))

@register.filter
def has_signed_agreement(user, property):
    """Check if user has signed agreement for property"""
    if not user or not user.is_authenticated:
        return False
    return SignedAgreement.objects.filter(tenant=user, property=property).exists()

@register.filter
def get_interest(user, property):
    """Get user's interest for a specific property"""
    if not user or not user.is_authenticated:
        return None
    try:
        return Interest.objects.get(tenant=user, property=property)
    except Interest.DoesNotExist:
        return None