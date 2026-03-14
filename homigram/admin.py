# core/admin.py
from django.contrib import admin
from django.urls import path
from django.shortcuts import render
from django.utils import timezone

# Import all models
from .models import (
    # User & Profile
    Profile,

    # Property related
    Property,
    PropertyFeature,
    PropertyImage,

    # Agreements & Inspections
    SignedAgreement,
    Inspection,

    # Financial
    Transaction,
    Escrow,
    WithdrawalRequest,

    # Interactions
    Interest,
    Reservation,
    OccupancyRequest,

    # Communication
    ChatMessage,

    # Reviews & Ratings
    PropertyReview,
    Rating,

    # Moderation
    Flag,
)


# ============================================
# Profile Admin
# ============================================
@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'user_type', 'wallet_balance', 'is_verified', 'email_verified', 'flag_count']
    list_filter = ['user_type', 'is_verified', 'email_verified']
    search_fields = ['user__username', 'user__email', 'phone', 'id_number']
    readonly_fields = ['verification_submitted_at', 'verified_at', 'flag_count']

    fieldsets = (
        ('User Information', {
            'fields': ('user', 'user_type', 'phone', 'wallet_balance')
        }),
        ('Identity Verification', {
            'fields': ('is_verified', 'id_type', 'id_number', 'id_document', 'passport_photo',
                       'verification_submitted_at', 'verified_at')
        }),
        ('Personal Information', {
            'fields': ('full_name_on_id', 'occupation', 'marital_status', 'religion', 'state_of_origin'),
            'classes': ('collapse',)
        }),
        ('Flagging', {
            'fields': ('flag_count', 'is_flagged', 'account_disabled', 'disabled_at'),
            'classes': ('collapse',)
        }),
    )

    actions = ['approve_verification', 'reject_verification']

    def approve_verification(self, request, queryset):
        for profile in queryset:
            profile.is_verified = True
            profile.verified_at = timezone.now()
            profile.save()
        self.message_user(request, f"{queryset.count()} profile(s) approved.")

    approve_verification.short_description = "Approve selected verification requests"

    def reject_verification(self, request, queryset):
        for profile in queryset:
            profile.is_verified = False
            profile.verification_submitted_at = None
            profile.save()
        self.message_user(request, f"{queryset.count()} profile(s) rejected.")

    reject_verification.short_description = "Reject selected verification requests"


# ============================================
# Property Feature Admin
# ============================================
@admin.register(PropertyFeature)
class PropertyFeatureAdmin(admin.ModelAdmin):
    list_display = ['name', 'icon']
    search_fields = ['name']


# ============================================
# Property Admin
# ============================================
@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ['title', 'landlord', 'price', 'city', 'is_available', 'occupancy_status']
    list_filter = ['is_available', 'occupancy_status', 'city', 'features']
    search_fields = ['title', 'address', 'city', 'description']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Basic Information', {
            'fields': ('landlord', 'title', 'description', 'price', 'inspection_fee')
        }),
        ('Location', {
            'fields': ('address', 'city', 'state', 'zipcode', 'latitude', 'longitude')
        }),
        ('Details', {
            'fields': ('bedrooms', 'bathrooms', 'sqft', 'features')
        }),
        ('Status', {
            'fields': ('is_available', 'occupancy_status', 'pending_occupancy_change')
        }),
        ('Documents', {
            'fields': ('rental_agreement',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


# ============================================
# Property Image Admin
# ============================================
@admin.register(PropertyImage)
class PropertyImageAdmin(admin.ModelAdmin):
    list_display = ['property', 'is_primary', 'image']
    list_filter = ['is_primary']
    search_fields = ['property__title']


# ============================================
# Signed Agreement Admin
# ============================================
@admin.register(SignedAgreement)
class SignedAgreementAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'property', 'signed_at']
    list_filter = ['signed_at']
    search_fields = ['tenant__username', 'property__title']
    readonly_fields = ['signed_at', 'ip_address']


# ============================================
# Inspection Admin
# ============================================
@admin.register(Inspection)
class InspectionAdmin(admin.ModelAdmin):
    list_display = ['user', 'property', 'paid_at', 'amount_paid', 'access_expires_at']
    list_filter = ['paid_at', 'access_expires_at']
    search_fields = ['user__username', 'property__title']


# ============================================
# Transaction Admin
# ============================================
@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['user', 'amount', 'transaction_type', 'reference', 'status', 'created_at']
    list_filter = ['transaction_type', 'status', 'created_at']
    search_fields = ['user__username', 'reference', 'description']
    readonly_fields = ['created_at']


# ============================================
# Interest Admin
# ============================================
@admin.register(Interest)
class InterestAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'property', 'status', 'created_at', 'expires_at']
    list_filter = ['status', 'created_at']
    search_fields = ['tenant__username', 'property__title']
    readonly_fields = ['created_at', 'responded_at']


# ============================================
# Escrow Admin
# ============================================
@admin.register(Escrow)
class EscrowAdmin(admin.ModelAdmin):
    list_display = ['id', 'property', 'tenant', 'landlord', 'amount', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['property__title', 'tenant__username', 'landlord__username']
    readonly_fields = ['created_at', 'updated_at']


# ============================================
# Reservation Admin
# ============================================
@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ['id', 'tenant', 'property', 'status', 'daily_fee', 'total_charged', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['tenant__username', 'property__title']
    readonly_fields = ['created_at', 'updated_at', 'last_charged_date']


# ============================================
# Occupancy Request Admin
# ============================================
@admin.register(OccupancyRequest)
class OccupancyRequestAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'property', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['tenant__username', 'property__title']


# ============================================
# Withdrawal Request Admin
# ============================================
@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    list_display = ['user', 'amount', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['user__username', 'account_name']


# ============================================
# Flag Admin
# ============================================
@admin.register(Flag)
class FlagAdmin(admin.ModelAdmin):
    list_display = ['flagged_user', 'flagged_by', 'reason', 'created_at']
    list_filter = ['reason', 'created_at']
    search_fields = ['flagged_user__username', 'flagged_by__username']


# ============================================
# Rating Admin
# ============================================
@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ['rater', 'rated_user', 'rating_type', 'score', 'created_at']
    list_filter = ['rating_type', 'score', 'created_at']
    search_fields = ['rater__username', 'rated_user__username']


# ============================================
# Property Review Admin
# ============================================
@admin.register(PropertyReview)
class PropertyReviewAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'property', 'rating', 'created_at']
    list_filter = ['rating', 'created_at']
    search_fields = ['tenant__username', 'property__title']


# ============================================
# Chat Message Admin
# ============================================
@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ['sender', 'recipient', 'property', 'timestamp', 'is_read']
    list_filter = ['is_read', 'timestamp']
    search_fields = ['sender__username', 'recipient__username', 'message']