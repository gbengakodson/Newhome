# core/models.py
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from datetime import timedelta
import uuid


# ============================================
# 1. BASE MODELS (No foreign keys or simple dependencies)
# ============================================

class PropertyFeature(models.Model):
    """Available features that can be attached to properties"""
    name = models.CharField(max_length=50)
    icon = models.CharField(max_length=50, blank=True)

    class Meta:
        verbose_name = "Property Feature"
        verbose_name_plural = "Property Features"

    def __str__(self):
        return self.name


# ============================================
# 2. USER-RELATED MODELS (Only reference User)
# ============================================

class Profile(models.Model):
    USER_TYPES = (
        ('tenant', 'Tenant'),
        ('landlord', 'Landlord'),
        ('visitor', 'Visitor'),
    )

    MARITAL_STATUS = (
        ('single', 'Single'),
        ('married', 'Married'),
        ('divorced', 'Divorced'),
        ('widowed', 'Widowed'),
    )

    RELIGION = (
        ('christianity', 'Christianity'),
        ('islam', 'Islam'),
        ('other', 'Other'),
        ('none', 'None'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    user_type = models.CharField(max_length=10, choices=USER_TYPES, default='visitor')
    email_verified = models.BooleanField(default=False)
    wallet_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    phone = models.CharField(max_length=15, blank=True)

    # Identity verification
    id_type = models.CharField(max_length=20, choices=[
        ('nin', 'NIN'),
        ('passport', 'International Passport'),
        ('driver_license', "Driver's License"),
    ], blank=True, null=True)
    id_number = models.CharField(max_length=50, blank=True)
    id_document = models.FileField(upload_to='verification/ids/', blank=True, null=True)
    passport_photo = models.ImageField(upload_to='verification/photos/', blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    verification_submitted_at = models.DateTimeField(blank=True, null=True)
    verified_at = models.DateTimeField(blank=True, null=True)

    # Tenant personal info
    full_name_on_id = models.CharField(max_length=100, blank=True)
    occupation = models.CharField(max_length=100, blank=True)
    marital_status = models.CharField(max_length=20, choices=MARITAL_STATUS, blank=True)
    religion = models.CharField(max_length=20, choices=RELIGION, blank=True)
    state_of_origin = models.CharField(max_length=50, blank=True)

    # Flagging
    flag_count = models.IntegerField(default=0)
    is_flagged = models.BooleanField(default=False)
    account_disabled = models.BooleanField(default=False)
    disabled_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} - {self.user_type}"

    def increment_flag(self):
        self.flag_count += 1
        if self.flag_count >= 7:
            self.account_disabled = True
            self.disabled_at = timezone.now()
        self.save()


# ============================================
# 3. PROPERTY MODELS (Reference User and PropertyFeature)
# ============================================

class Property(models.Model):
    OCCUPANCY_STATUS = (
        ('vacant', 'Vacant'),
        ('occupied', 'Occupied'),
    )

    landlord = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'profile__user_type': 'landlord'})
    title = models.CharField(max_length=200)
    description = models.TextField()
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    zipcode = models.CharField(max_length=20)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    bedrooms = models.IntegerField()
    bathrooms = models.DecimalField(max_digits=3, decimal_places=1)
    sqft = models.IntegerField()
    features = models.ManyToManyField(PropertyFeature, blank=True, related_name='properties')
    is_available = models.BooleanField(default=True)
    occupancy_status = models.CharField(max_length=10, choices=OCCUPANCY_STATUS, default='vacant')
    pending_occupancy_change = models.CharField(max_length=10, choices=OCCUPANCY_STATUS, blank=True, null=True)
    inspection_fee = models.DecimalField(max_digits=6, decimal_places=2, default=5.00)
    rental_agreement = models.FileField(upload_to='rental_agreements/', blank=True, null=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    reservation_status = models.CharField(max_length=20,choices=[('available', 'Available'),('reserved', 'Reserved'),('occupied', 'Occupied') ],default='available')

    def __str__(self):
        return self.title

    @property
    def daily_reservation_fee(self):
        return self.price / 365

    @property
    def full_address(self):
        return f"{self.address}, {self.city}, {self.state} {self.zipcode}"




class PropertyImage(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='properties/')
    is_primary = models.BooleanField(default=False)

    def __str__(self):
        return f"Image for {self.property.title}"


# core/models.py

class PropertyReview(models.Model):
    """Tenant reviews a property after staying"""
    tenant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='property_reviews')
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='reviews')
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)])  # 1-5 stars
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['tenant', 'property']  # One review per tenant per property
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.tenant.username} - {self.property.title} - {self.rating}★"


class Rating(models.Model):
    """Users rate each other (tenant<->landlord)"""
    RATING_TYPES = (
        ('tenant_to_landlord', 'Tenant to Landlord'),
        ('landlord_to_tenant', 'Landlord to Tenant'),
    )

    rater = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ratings_given')
    rated_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ratings_received')
    rating_type = models.CharField(max_length=20, choices=RATING_TYPES)
    score = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    comment = models.TextField(blank=True)
    property = models.ForeignKey(Property, on_delete=models.CASCADE, null=True, blank=True, related_name='ratings')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['rater', 'rated_user', 'rating_type', 'property']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.rater.username} rated {self.rated_user.username}: {self.score}★"


# ============================================
# 4. TRANSACTION MODEL (References User and Property)
# ============================================

class Transaction(models.Model):
    TRANSACTION_TYPES = (
        ('deposit', 'Deposit'),
        ('inspection', 'Inspection Fee'),
        ('inspection_share_landlord', 'Inspection Share (Landlord)'),
        ('inspection_share_system', 'Inspection Share (System)'),
        ('reservation', 'Reservation Fee'),
        ('rent_deposit', 'Rent Deposit'),
        ('withdrawal', 'Withdrawal'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(max_length=25, choices=TRANSACTION_TYPES)
    reference = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=20, default='pending')
    description = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # For inspection payments
    property = models.ForeignKey(Property, null=True, blank=True, on_delete=models.SET_NULL)
    landlord = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name='landlord_transactions')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.transaction_type} - {self.amount}"


# ============================================
# 5. INSPECTION MODEL (References User, Property, Transaction)
# ============================================

class Inspection(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='inspections')
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='inspections')
    paid_at = models.DateTimeField(auto_now_add=True)
    amount_paid = models.DecimalField(max_digits=6, decimal_places=2)
    access_expires_at = models.DateTimeField(null=True, blank=True)
    transaction = models.ForeignKey(Transaction, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='inspection')

    class Meta:
        # Remove this line:
        # unique_together = ['user', 'property']

        # Add ordering instead
        ordering = ['-paid_at']

    def save(self, *args, **kwargs):
        if not self.access_expires_at:
            self.access_expires_at = timezone.now() + timedelta(hours=24)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} inspected {self.property.title} on {self.paid_at}"

# ============================================
# 6. SIGNED AGREEMENT MODEL (References User, Property)
# ============================================

class SignedAgreement(models.Model):
    tenant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='signed_agreements')
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='signed_agreements')
    agreement_file = models.FileField(upload_to='signed_agreements/')
    signed_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    signature_data = models.TextField(blank=True)

    class Meta:
        unique_together = ['tenant', 'property']

    def __str__(self):
        return f"Agreement for {self.property} signed by {self.tenant.username}"


# ============================================
# 7. FLAG MODEL (References User, Property)
# ============================================

class Flag(models.Model):
    FLAG_REASONS = (
        ('fake', 'Fake Listing'),
        ('scam', 'Scam/Fraud'),
        ('harassment', 'Harassment'),
        ('misconduct', 'Misconduct'),
        ('no_response', 'No Response to Interest'),
        ('other', 'Other'),
    )

    flagged_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='flags_received')
    flagged_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='flags_made')
    reason = models.CharField(max_length=20, choices=FLAG_REASONS)
    description = models.TextField()
    property = models.ForeignKey(Property, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['flagged_user', 'flagged_by']

    def __str__(self):
        return f"Flag on {self.flagged_user.username} by {self.flagged_by.username}"


# ============================================
# 8. INTEREST MODEL (References User, Property, uses Flag)
# ============================================

class Interest(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending Review'),
        ('approved', 'Approved - Extended Access'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired - No Response'),
    )

    tenant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='interests')
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='interests')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()
    landlord_flagged = models.BooleanField(default=False)
    flag_added_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['tenant', 'property']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.tenant.username} interested in {self.property.title} - {self.status}"

    def approve(self):
        """Approve interest and extend inspection access"""
        self.status = 'approved'
        self.responded_at = timezone.now()
        self.save()

        # Extend tenant's inspection access for 7 days
        try:
            inspection = Inspection.objects.get(user=self.tenant, property=self.property)
            inspection.access_expires_at = timezone.now() + timedelta(days=7)
            inspection.save()
        except Inspection.DoesNotExist:
            # Create inspection if it doesn't exist (shouldn't happen)
            Inspection.objects.create(
                user=self.tenant,
                property=self.property,
                amount_paid=self.property.inspection_fee,
                access_expires_at=timezone.now() + timedelta(days=7)
            )

    def reject(self):
        """Reject interest"""
        self.status = 'rejected'
        self.responded_at = timezone.now()
        self.save()

    def expire_and_flag(self):
        self.status = 'expired'
        self.save()

        landlord = self.property.landlord
        landlord.profile.flag_count += 1
        landlord.profile.save()

        Flag.objects.create(
            flagged_user=landlord,
            flagged_by=self.tenant,
            reason='no_response',
            description=f'Failed to respond to interest in {self.property.title} within 7 days',
            property=self.property
        )

        self.landlord_flagged = True
        self.flag_added_at = timezone.now()
        self.save()


# ============================================
# 9. ESCROW MODEL (References User, Property, Interest)
# ============================================

# core/models.py - Escrow model

class Escrow(models.Model):
    ESCROW_TYPES = (
        ('occupancy', 'Occupancy Deposit'),
        ('reservation', 'Reservation Deposit'),
    )

    tenant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='escrows_as_tenant')
    landlord = models.ForeignKey(User, on_delete=models.CASCADE, related_name='escrows_as_landlord')
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='escrows')
    interest = models.OneToOneField(Interest, on_delete=models.CASCADE, related_name='escrow', null=True, blank=True)

    escrow_type = models.CharField(max_length=20, choices=ESCROW_TYPES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)  # 20% of annual rent
    annual_rent = models.DecimalField(max_digits=10, decimal_places=2)  # Full annual rent

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # For occupancy: rent paid offline flag
    offline_rent_paid = models.BooleanField(default=False)  # Landlord confirms offline payment

    # Release approvals (for move-out)
    tenant_approved = models.BooleanField(default=False)
    landlord_approved = models.BooleanField(default=False)

    # Evidence uploads
    tenant_evidence = models.FileField(upload_to='escrow/tenant/', blank=True, null=True)
    landlord_evidence = models.FileField(upload_to='escrow/landlord/', blank=True, null=True)

    status = models.CharField(max_length=25, choices=[
        ('held', 'Held in Escrow'),
        ('released_to_landlord', 'Released to Landlord'),
        ('refunded_to_tenant', 'Refunded to Tenant'),
        ('disputed', 'Disputed'),
    ], default='held')

    released_at = models.DateTimeField(null=True, blank=True)
    released_to = models.CharField(max_length=10, choices=[('tenant', 'Tenant'), ('landlord', 'Landlord')], null=True,
                                   blank=True)

    class Meta:
        verbose_name_plural = "Escrows"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_escrow_type_display()} for {self.property.title} - ₦{self.amount}"


    def both_approved(self):
        return self.tenant_approved and self.landlord_approved

    def release_to_landlord(self):
        from django.utils import timezone
        from .models import Transaction

        if not self.both_approved():
            raise ValueError("Both parties must approve before release")

        self.landlord.profile.wallet_balance += self.amount
        self.landlord.profile.save()

        self.status = 'released_to_landlord'
        self.released_at = timezone.now()
        self.released_to = 'landlord'
        self.save()

        Transaction.objects.create(
            user=self.landlord,
            amount=self.amount,
            transaction_type='rent_deposit',
            reference=f"ESC-REL-{self.id}-{timezone.now().strftime('%Y%m%d%H%M%S')}",
            status='success',
            description=f'{self.get_escrow_type_display()} released',
            property=self.property
        )

    def refund_to_tenant(self):
        from django.utils import timezone
        from .models import Transaction

        if not self.both_approved():
            raise ValueError("Both parties must approve before refund")

        self.tenant.profile.wallet_balance += self.amount
        self.tenant.profile.save()

        self.status = 'refunded_to_tenant'
        self.released_at = timezone.now()
        self.released_to = 'tenant'
        self.save()

        Transaction.objects.create(
            user=self.tenant,
            amount=self.amount,
            transaction_type='rent_deposit',
            reference=f"ESC-REF-{self.id}-{timezone.now().strftime('%Y%m%d%H%M%S')}",
            status='success',
            description=f'{self.get_escrow_type_display()} refunded',
            property=self.property
        )
# ============================================
# 10. OCCUPANCY REQUEST MODEL (References User, Property)
# ============================================

class OccupancyRequest(models.Model):
    tenant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='occupancy_requests')
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='occupancy_requests')
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], default='pending')

    # Snapshot of tenant info
    tenant_full_name = models.CharField(max_length=100)
    tenant_occupation = models.CharField(max_length=100)
    tenant_marital_status = models.CharField(max_length=20)
    tenant_religion = models.CharField(max_length=20)
    tenant_state_of_origin = models.CharField(max_length=50)
    tenant_phone = models.CharField(max_length=15)
    tenant_email = models.EmailField()

    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"Occupancy request by {self.tenant.username} for {self.property.title}"


# ============================================
# 11. RESERVATION MODEL (References User, Property)
# ============================================

class Reservation(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending Approval'),
        ('active', 'Active'),
        ('cancelled_by_tenant', 'Cancelled by Tenant'),
        ('cancelled_by_landlord', 'Cancelled by Landlord'),
        ('expired', 'Expired - Insufficient Funds'),
        ('completed', 'Completed - Moved to Occupancy'),
    )

    tenant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reservations')
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='reservations')
    interest = models.OneToOneField('Interest', on_delete=models.CASCADE, related_name='reservation', null=True,
                                    blank=True)

    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Approval tracking
    approved_by_landlord = models.BooleanField(default=False)
    approved_at = models.DateTimeField(null=True, blank=True)

    # Reservation period
    start_date = models.DateTimeField(null=True, blank=True)
    expected_end_date = models.DateTimeField(null=True, blank=True)
    actual_end_date = models.DateTimeField(null=True, blank=True)

    # Fee tracking
    daily_fee = models.DecimalField(max_digits=10, decimal_places=2)
    total_charged = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    last_charged_date = models.DateTimeField(null=True, blank=True)

    # Notification flags
    low_balance_notified = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        unique_together = ['tenant', 'property']  # One active reservation per tenant per property

    def __str__(self):
        return f"{self.tenant.username} reserving {self.property.title} - {self.status}"

    def approve(self):
        """Landlord approves the reservation"""
        from django.utils import timezone

        self.status = 'active'
        self.approved_by_landlord = True
        self.approved_at = timezone.now()
        self.start_date = timezone.now()
        self.save()

    def cancel(self, cancelled_by):
        """Cancel reservation"""
        from django.utils import timezone

        if cancelled_by == 'tenant':
            self.status = 'cancelled_by_tenant'
        elif cancelled_by == 'landlord':
            self.status = 'cancelled_by_landlord'

        self.actual_end_date = timezone.now()
        self.save()

    def charge_daily_fee(self):
        """Charge daily fee from tenant's wallet"""
        from django.utils import timezone
        from .models import Transaction

        if self.status != 'active':
            return False, "Reservation not active"

        if self.tenant.profile.wallet_balance < self.daily_fee:
            self.low_balance_notified = True
            self.save()
            return False, "Insufficient balance"

        # Deduct from tenant
        self.tenant.profile.wallet_balance -= self.daily_fee
        self.tenant.profile.save()

        # Credit to landlord
        self.property.landlord.profile.wallet_balance += self.daily_fee
        self.property.landlord.profile.save()

        # Update totals
        self.total_charged += self.daily_fee
        self.last_charged_date = timezone.now()
        self.low_balance_notified = False
        self.save()

        # Create transaction records
        Transaction.objects.create(
            user=self.tenant,
            amount=-self.daily_fee,
            transaction_type='reservation',
            reference=f"RES-{self.id}-{timezone.now().strftime('%Y%m%d%H%M%S')}",
            status='success',
            description=f'Daily reservation fee for {self.property.title}',
            property=self.property
        )

        Transaction.objects.create(
            user=self.property.landlord,
            amount=self.daily_fee,
            transaction_type='reservation',
            reference=f"RES-L-{self.id}-{timezone.now().strftime('%Y%m%d%H%M%S')}",
            status='success',
            description=f'Daily reservation fee from {self.tenant.username}',
            property=self.property
        )

        return True, "Fee charged successfully"





# ============================================
# 12. WITHDRAWAL REQUEST MODEL (References User)
# ============================================

class WithdrawalRequest(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='withdrawals')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    bank_name = models.CharField(max_length=100)
    account_number = models.CharField(max_length=20)
    account_name = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('processed', 'Processed'),
        ('failed', 'Failed')
    ], default='pending')
    reference = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"Withdrawal {self.amount} for {self.user.username}"


# ============================================
# 13. REVIEW & RATING MODELS (References User, Property)
# ============================================

class PropertyReview(models.Model):
    tenant = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'profile__user_type': 'tenant'})
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='reviews')
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['tenant', 'property']

    def __str__(self):
        return f"{self.tenant.username} - {self.property.title} - {self.rating}★"


class Rating(models.Model):
    RATING_TYPES = (
        ('tenant_to_landlord', 'Tenant to Landlord'),
        ('landlord_to_tenant', 'Landlord to Tenant'),
    )

    rater = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ratings_given')
    rated_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ratings_received')
    rating_type = models.CharField(max_length=20, choices=RATING_TYPES)
    score = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    comment = models.TextField(blank=True)
    property = models.ForeignKey(Property, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['rater', 'rated_user', 'rating_type', 'property']

    def __str__(self):
        return f"{self.rater.username} rated {self.rated_user.username}: {self.score}★"


# ============================================
# 14. CHAT MESSAGE MODEL (References User, Property)
# ============================================

class ChatMessage(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    property = models.ForeignKey(Property, on_delete=models.CASCADE, null=True, blank=True,
                                 related_name='chat_messages')
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"From {self.sender} to {self.recipient}: {self.message[:40]}"

    def mark_as_read(self):
        self.is_read = True
        self.save()

# ============================================
# SIGNALS (Keep at the bottom)
# ============================================

from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()