from django import template
from homigram.models import SignedAgreement, Interest, Escrow
from django.utils.safestring import mark_safe
import json

register = template.Library()

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

@register.filter
def has_escrow(property, user):
    """Check if user has an escrow for this property"""
    if not user or not user.is_authenticated:
        return False
    return Escrow.objects.filter(property=property, tenant=user).exists()

@register.filter
def get_escrow(property, user):
    """Get escrow for property and user if it exists"""
    if not user or not user.is_authenticated:
        return None
    try:
        return Escrow.objects.get(property=property, tenant=user)
    except Escrow.DoesNotExist:
        return None

# core/templatetags/property_extras.py

@register.filter
def jsonify(obj):
    """Convert object to JSON safe string"""
    return mark_safe(json.dumps(obj))


@register.filter
def multiply(value, arg):
    """Multiply the value by the argument"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0