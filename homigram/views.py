
# core/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.utils import timezone
from django.db import transaction as db_transaction
from django.urls import reverse
from datetime import timedelta
import uuid
from .decorators import landlord_verified_required
from django.db.models import Sum, Count, Avg
import requests
from django.conf import settings
from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User
from .decorators import verified_and_funded_required

# core/views.py
from django.http import JsonResponse
from .models import ChatMessage
from django.db.models import Q, Sum

# Import all models
from .models import (
    Profile, Property, PropertyFeature, PropertyImage,
    SignedAgreement, Inspection, Transaction, Escrow,
    Interest, Flag, Rating, PropertyReview,
    OccupancyRequest, Reservation, WithdrawalRequest, ChatMessage
)

# Import forms
from .forms import UserRegistrationForm, PropertyForm, VerificationSubmissionForm

# Import decorators
from .decorators import (
    tenant_required,
    landlord_required,
    verified_required,
    tenant_verified_required,
    landlord_verified_required
)


# Import utilities
# Instead of: from .utils import send_verification_email
from homigram.utils import send_verification_email, account_activation_token

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Avg, Sum, Count
from django.utils import timezone
from .models import User, Profile, Property, Interest, Escrow, Reservation, Transaction, Rating, PropertyReview, \
    Inspection, ChatMessage, OccupancyRequest


@login_required
def profile_view(request):
    """Unified profile view for both tenants and landlords"""
    user = request.user
    profile = user.profile

    # Common data for all users
    transactions = Transaction.objects.filter(user=user).order_by('-created_at')[:10]

    # Reviews received
    if profile.user_type == 'landlord':
        reviews_received = Rating.objects.filter(
            rated_user=user,
            rating_type='tenant_to_landlord'
        ).select_related('rater', 'property')
        avg_rating = reviews_received.aggregate(Avg('score'))['score__avg'] or 0
    else:
        reviews_received = Rating.objects.filter(
            rated_user=user,
            rating_type='landlord_to_tenant'
        ).select_related('rater', 'property')
        avg_rating = reviews_received.aggregate(Avg('score'))['score__avg'] or 0

    # Recent activities
    recent_activities = []

    # Add interests
    for interest in Interest.objects.filter(tenant=user).order_by('-created_at')[:3]:
        recent_activities.append({
            'title': f'Interest in {interest.property.title}',
            'description': f'Status: {interest.status}',
            'timestamp': interest.created_at,
            'color': 'primary',
            'icon': 'fa-thumbs-up'
        })

    # Add escrows
    for escrow in Escrow.objects.filter(tenant=user).order_by('-created_at')[:3]:
        recent_activities.append({
            'title': f'{escrow.get_escrow_type_display()} Deposit',
            'description': f'Amount: ₦{escrow.amount}',
            'timestamp': escrow.created_at,
            'color': 'warning',
            'icon': 'fa-lock'
        })

    # Add reservations
    for res in Reservation.objects.filter(tenant=user).order_by('-created_at')[:3]:
        recent_activities.append({
            'title': f'Reservation for {res.property.title}',
            'description': f'Status: {res.status}',
            'timestamp': res.created_at,
            'color': 'info',
            'icon': 'fa-calendar-alt'
        })

    # Sort activities by timestamp
    recent_activities.sort(key=lambda x: x['timestamp'], reverse=True)
    recent_activities = recent_activities[:10]

    # Stats
    total_inspections = Inspection.objects.filter(user=user).count()
    approved_interests = Interest.objects.filter(tenant=user, status='approved').count()
    active_escrows = Escrow.objects.filter(tenant=user, status='held').count()
    active_reservations = Reservation.objects.filter(tenant=user, status='active').count()

    # For landlords, get their properties
    properties = None
    if profile.user_type == 'landlord':
        properties = Property.objects.filter(landlord=user).order_by('-created_at')[:6]

    context = {
        'profile': profile,
        'transactions': transactions,
        'reviews_received': reviews_received,
        'avg_rating': round(avg_rating, 1),
        'total_ratings': reviews_received.count(),
        'recent_activities': recent_activities,
        'total_inspections': total_inspections,
        'approved_interests': approved_interests,
        'active_escrows': active_escrows,
        'active_reservations': active_reservations,
        'properties': properties,
        'now': timezone.now(),
    }

    return render(request, 'profile.html', context)


@login_required
def update_profile(request):
    """Handle profile updates"""
    if request.method == 'POST':
        user = request.user
        profile = user.profile

        # Update user fields
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.save()

        # Update profile fields
        profile.phone = request.POST.get('phone', profile.phone)
        profile.city = request.POST.get('city', profile.city)
        profile.state = request.POST.get('state', profile.state)

        if profile.user_type == 'tenant':
            profile.occupation = request.POST.get('occupation', profile.occupation)
            profile.marital_status = request.POST.get('marital_status', profile.marital_status)
            profile.religion = request.POST.get('religion', profile.religion)
            profile.state_of_origin = request.POST.get('state_of_origin', profile.state_of_origin)

        # Handle photo upload
        if 'passport_photo' in request.FILES:
            profile.passport_photo = request.FILES['passport_photo']

        profile.save()

        messages.success(request, 'Profile updated successfully!')
        return redirect('profile_view')

    return redirect('profile_view')




def home(request):
    """
    Home page with featured properties
    """
    # Get featured properties (most recent, available)
    featured_properties = Property.objects.filter(
        is_available=True
    ).order_by('-created_at')[:6]

    # You might want to add counts for different property types
    property_counts = {
        'apartments': Property.objects.filter(features__name='Apartment').count(),
        'houses': Property.objects.filter(features__name='House').count(),
        'lands': Property.objects.filter(features__name='Land').count(),
        'commercial': Property.objects.filter(features__name='Commercial').count(),
    }
    unread_count = 0
    if request.user.is_authenticated:
        unread_count = ChatMessage.objects.filter(
            recipient=request.user,
            is_read=False
        ).count()

    context = {
        'featured_properties': featured_properties,
        'property_counts': property_counts,
        'unread_messages_count': unread_count,
    }
    # Add paid inspections for logged-in tenant
    if request.user.is_authenticated and request.user.profile.user_type == 'tenant':
        paid_inspections = Inspection.objects.filter(
            user=request.user,
            access_expires_at__gt=timezone.now()
        ).values_list('property_id', flat=True)
        context['paid_inspections'] = list(paid_inspections)

    return render(request, 'index.html', context)


from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Profile


class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        fields = UserCreationForm.Meta.fields + ('email',)


from django.contrib.sites.shortcuts import get_current_site
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.conf import settings
from .utils import account_activation_token


def register(request):
    if request.method == 'POST':
        # ... your form handling code ...

        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False  # Important: Deactivate until email verified
            user.save()

            # Create profile
            Profile.objects.create(
                user=user,
                user_type=request.POST.get('user_type', 'tenant'),
                phone=request.POST.get('phone', ''),
                email_verified=False
            )

            # Send verification email
            current_site = get_current_site(request)
            mail_subject = 'Activate Your Homigram.ng Account'

            message = render_to_string('verification_email.html', {
                'user': user,
                'domain': current_site.domain,
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'token': account_activation_token.make_token(user),
                'protocol': 'https',
            })

            send_mail(
                mail_subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )

            messages.success(request, 'Please check your email to verify your account.')
            return redirect('login')

    # ... rest of your view



def verify_email(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    if user and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        user.profile.email_verified = True
        user.profile.save()
        messages.success(request, 'Email verified. You can now log in.')
    else:
        messages.error(request, 'Verification link invalid.')
    return redirect('login')


User = get_user_model()

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Avg, Sum, Count
from django.utils import timezone
from .models import User, Profile, Property, Interest, Escrow, Reservation, Transaction, Rating, PropertyReview


def tenant_profile(request, tenant_id):
    """
    Complete tenant profile view with wallet balance and all相关信息
    """
    # Get the tenant user
    tenant = get_object_or_404(User, id=tenant_id, profile__user_type='tenant')

    # Get profile data
    profile = tenant.profile

    # Get wallet balance
    wallet_balance = profile.wallet_balance

    # Get all transactions
    transactions = Transaction.objects.filter(user=tenant).order_by('-created_at')[:10]

    # Calculate total spent
    total_spent = Transaction.objects.filter(
        user=tenant,
        transaction_type__in=['inspection', 'rent_deposit', 'reservation'],
        status='success'
    ).aggregate(total=Sum('amount'))['total'] or 0
    total_spent = abs(total_spent)  # Convert negative to positive

    # Get all interests
    interests = Interest.objects.filter(tenant=tenant).select_related('property', 'property__landlord')

    # Get approved interests count
    approved_interests = interests.filter(status='approved').count()

    # Get pending interests
    pending_interests = interests.filter(status='pending').count()

    # Get escrows
    escrows = Escrow.objects.filter(tenant=tenant).select_related('property', 'landlord')

    # Get active escrows (held)
    active_escrows = escrows.filter(status='held').count()

    # Get total in escrow
    total_in_escrow = escrows.filter(status='held').aggregate(total=Sum('amount'))['total'] or 0

    # Get reservations
    reservations = Reservation.objects.filter(tenant=tenant).select_related('property')

    # Get active reservations
    active_reservations = reservations.filter(status='active').count()

    # Get inspections (if you have an Inspection model)
    from .models import Inspection
    inspections = Inspection.objects.filter(user=tenant).select_related('property')
    total_inspections = inspections.count()

    # Get ratings received (from landlords)
    ratings_received = Rating.objects.filter(
        rated_user=tenant,
        rating_type='landlord_to_tenant'
    ).select_related('rater', 'property')

    # Calculate average rating
    avg_rating = ratings_received.aggregate(Avg('score'))['score__avg'] or 0

    # Get reviews written by tenant (about properties)
    reviews_written = PropertyReview.objects.filter(tenant=tenant).select_related('property')

    # Get current date for template
    now = timezone.now()

    context = {
        # Basic info
        'tenant': tenant,
        'profile': profile,
        'wallet_balance': wallet_balance,

        # Financial stats
        'total_spent': total_spent,
        'total_in_escrow': total_in_escrow,
        'transactions': transactions,

        # Interest stats
        'interests': interests,
        'total_interests': interests.count(),
        'approved_interests': approved_interests,
        'pending_interests': pending_interests,

        # Escrow stats
        'escrows': escrows,
        'active_escrows': active_escrows,
        'total_escrows': escrows.count(),

        # Reservation stats
        'reservations': reservations,
        'active_reservations': active_reservations,
        'total_reservations': reservations.count(),

        # Inspection stats
        'inspections': inspections,
        'total_inspections': total_inspections,

        # Rating stats
        'ratings_received': ratings_received,
        'avg_rating': round(avg_rating, 1),
        'total_ratings': ratings_received.count(),
        'reviews_written': reviews_written,

        # Date
        'now': now,
    }

    return render(request, 'tenant_profile.html', context)# core/views.py



@login_required
def tenant_dashboard(request):
    if request.user.profile.user_type != 'tenant':
        return redirect('home')

    now = timezone.now()

    # Get tenant's transactions
    transactions = Transaction.objects.filter(
        user=request.user
    ).order_by('-created_at')[:20]

    # Get properties the tenant has inspected
    inspections = Inspection.objects.filter(
        user=request.user
    ).select_related('property').order_by('-paid_at')

    # Calculate total spent
    total_spent = inspections.aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0

    # Calculate active inspections
    active_inspections = inspections.filter(access_expires_at__gt=now).count()

    # Get active escrows
    active_escrows = Escrow.objects.filter(
        tenant=request.user,
        status='held'
    ).select_related('property', 'landlord')

    # Calculate total in escrow
    total_in_escrow = active_escrows.aggregate(Sum('amount'))['amount__sum'] or 0

    # Get active reservations
    active_reservations = Reservation.objects.filter(
        tenant=request.user,
        status='active'
    ).select_related('property')

    # Calculate days for each reservation
    for reservation in active_reservations:
        if reservation.start_date:
            reservation.days_reserved = (now - reservation.start_date).days
        else:
            reservation.days_reserved = 0

    # Get recommended properties (based on user's inspection history)
    if inspections.exists():
        # Get most common city from user's inspections
        most_common_city = inspections.values('property__city').annotate(
            count=Count('property__city')
        ).order_by('-count').first()

        if most_common_city and most_common_city['property__city']:
            city = most_common_city['property__city']
            recommended_properties = Property.objects.filter(
                city=city,
                is_available=True
            ).exclude(
                inspections__user=request.user
            ).distinct()[:4]
        else:
            recommended_properties = Property.objects.filter(
                is_available=True
            ).order_by('-created_at')[:4]
    else:
        # If no inspections, show newest properties
        recommended_properties = Property.objects.filter(
            is_available=True
        ).order_by('-created_at')[:4]

    # Calculate spending percentages for chart
    inspection_total = Transaction.objects.filter(
        user=request.user,
        transaction_type='inspection',
        status='success'
    ).aggregate(Sum('amount'))['amount__sum'] or 0

    deposit_total = Transaction.objects.filter(
        user=request.user,
        transaction_type='rent_deposit',
        status='success'
    ).aggregate(Sum('amount'))['amount__sum'] or 0

    reservation_total = Transaction.objects.filter(
        user=request.user,
        transaction_type='reservation',
        status='success'
    ).aggregate(Sum('amount'))['amount__sum'] or 0

    # Use absolute values for calculations (transactions can be negative)
    inspection_abs = abs(inspection_total)
    deposit_abs = abs(deposit_total)
    reservation_abs = abs(reservation_total)

    total_all = inspection_abs + deposit_abs + reservation_abs

    if total_all > 0:
        inspection_percentage = int((inspection_abs / total_all) * 100)
        deposit_percentage = int((deposit_abs / total_all) * 100)
        reservation_percentage = 100 - inspection_percentage - deposit_percentage
    else:
        inspection_percentage = 45
        deposit_percentage = 30
        reservation_percentage = 25

    # Get weekly spending data for chart
    week_days = []
    week_data = []
    for i in range(6, -1, -1):
        day = now - timedelta(days=i)
        week_days.append(day.strftime('%a'))

        # Get total spending for that day
        day_start = day.replace(hour=0, minute=0, second=0)
        day_end = day.replace(hour=23, minute=59, second=59)

        day_spending = Transaction.objects.filter(
            user=request.user,
            created_at__range=[day_start, day_end],
            status='success'
        ).aggregate(Sum('amount'))['amount__sum'] or 0

        # Convert to float for JSON serialization
        week_data.append(float(abs(day_spending)))

    # Recent activities (combine different actions)
    recent_activities = []

    # Add recent inspections
    for insp in inspections[:3]:
        recent_activities.append({
            'title': f'Inspected {insp.property.title}',
            'description': f'Paid ₦{insp.amount_paid} for inspection',
            'timestamp': insp.paid_at,
            'color': 'info',
            'icon': 'fa-eye'
        })

    # Add recent escrows
    for esc in active_escrows[:2]:
        recent_activities.append({
            'title': f'{esc.get_escrow_type_display()} Deposit',
            'description': f'₦{esc.amount} held in escrow for {esc.property.title}',
            'timestamp': esc.created_at,
            'color': 'warning',
            'icon': 'fa-lock'
        })

    # Add recent reservations
    for res in active_reservations[:2]:
        recent_activities.append({
            'title': f'Reserved {res.property.title}',
            'description': f'Daily fee: ₦{res.daily_fee}',
            'timestamp': res.start_date or res.created_at,
            'color': 'success',
            'icon': 'fa-calendar-alt'
        })

    # Sort activities by timestamp (most recent first)
    recent_activities.sort(key=lambda x: x['timestamp'], reverse=True)
    recent_activities = recent_activities[:5]

    # Get favorites (placeholder - you'll need a Favorites model)
    favorites = []

    # Total properties count for stats
    total_properties = Property.objects.filter(is_available=True).count()

    unread_count = 0
    if request.user.is_authenticated:
        unread_count = ChatMessage.objects.filter(
            recipient=request.user,
            is_read=False
        ).count()

    context = {
        'wallet_balance': request.user.profile.wallet_balance,
        'transactions': transactions,
        'inspections': inspections,
        'total_spent': total_spent,
        'active_inspections': active_inspections,
        'active_escrows': active_escrows,
        'total_in_escrow': total_in_escrow,
        'active_reservations': active_reservations,
        'recommended_properties': recommended_properties,
        'recent_activities': recent_activities,
        'favorites': favorites,
        'total_properties': total_properties,
        'now': now,
        # Chart data - all properly formatted for JSON
        'week_days': week_days,
        'week_data': week_data,  # Now as floats
        'inspection_percentage': inspection_percentage,
        'deposit_percentage': deposit_percentage,
        'reservation_percentage': reservation_percentage,
        'unread_messages_count': unread_count,
    }

    # Add paid inspections
    paid_inspections = Inspection.objects.filter(
        user=request.user,
        access_expires_at__gt=timezone.now()
    ).values_list('property_id', flat=True)
    context['paid_inspections'] = list(paid_inspections)

    return render(request, 'tenant_dashboard.html', context)


@login_required
def secure_property_detail(request, property_id):
    """
    Secure property detail view that checks for valid inspection access
    """
    property = get_object_or_404(Property, id=property_id)

    # Check if user has valid inspection
    has_valid_access = False
    inspection = None

    if request.user == property.landlord:
        # Landlord always has access to own property
        has_valid_access = True
    else:
        # Get most recent inspection
        inspections = Inspection.objects.filter(
            user=request.user,
            property=property
        ).order_by('-paid_at')

        if inspections.exists():
            inspection = inspections.first()
            if inspection.access_expires_at > timezone.now():
                has_valid_access = True
            else:
                # Access expired - redirect to payment
                messages.warning(request,
                                 f'Your inspection access has expired. Please pay again to view this property.')
                return redirect('pay_inspection_before_view', property_id=property.id)
        else:
            # No inspection - redirect to payment
            messages.info(request, 'You need to pay the inspection fee to view this property.')
            return redirect('pay_inspection_before_view', property_id=property.id)

    if not has_valid_access and request.user != property.landlord:
        messages.error(request, 'You do not have permission to view this property.')
        return redirect('property_list')

    # Get tenant's interest if any
    interest = None
    if request.user.is_authenticated and request.user.profile.user_type == 'tenant':
        try:
            interest = Interest.objects.get(tenant=request.user, property=property)
        except Interest.DoesNotExist:
            pass

    # Calculate deposit amount (20% of annual rent)
    annual_rent = property.price * Decimal('12')
    deposit_amount = annual_rent * Decimal('0.2')

    # Get featured property
    featured_property = Property.objects.filter(
        is_available=True
    ).exclude(id=property.id).order_by('-created_at').first()

    # Get recently added properties
    recent_properties = Property.objects.filter(
        is_available=True
    ).exclude(id=property.id).order_by('-created_at')[:3]

    # Get related properties
    related_properties = Property.objects.filter(
        is_available=True,
        city=property.city
    ).exclude(id=property.id)[:4]

    # Check if user can review
    user_can_review = False
    if request.user.is_authenticated and request.user.profile.user_type == 'tenant':
        has_occupied = OccupancyRequest.objects.filter(
            tenant=request.user,
            property=property,
            status='approved'
        ).exists()
        has_reviewed = PropertyReview.objects.filter(
            tenant=request.user,
            property=property
        ).exists()
        user_can_review = has_occupied and not has_reviewed

    context = {
        'property': property,
        'has_paid': has_valid_access,
        'inspection': inspection,
        'interest': interest,
        'deposit_amount': deposit_amount,
        'annual_rent': annual_rent,
        'featured_property': featured_property,
        'recent_properties': recent_properties,
        'related_properties': related_properties,
        'user_can_review': user_can_review,
        'now': timezone.now(),
    }

    return render(request, 'property_detail.html', context)



def landlord_profile(request, landlord_id):
    """
    Public profile page for landlord showing ratings
    """
    try:
        landlord = get_object_or_404(User, id=landlord_id, profile__user_type='landlord')
    except:
        messages.error(request, 'Landlord not found.')
        return redirect('home')

    # Get all ratings received from tenants
    ratings = Rating.objects.filter(
        rated_user=landlord,
        rating_type='tenant_to_landlord'
    ).select_related('rater', 'property')

    # Calculate average
    avg_rating = ratings.aggregate(Avg('score'))['score__avg'] or 0
    total_ratings = ratings.count()

    # Get properties owned
    properties = Property.objects.filter(landlord=landlord, is_available=True)

    context = {
        'landlord': landlord,
        'ratings': ratings,
        'avg_rating': round(avg_rating, 1),
        'total_ratings': total_ratings,
        'properties': properties,
    }
    return render(request, 'landlord_profile.html', context)

# core/views.py
@login_required
def landlord_dashboard(request):
    # Clear messages at start
    storage = messages.get_messages(request)
    storage.used = True
    # Security: Only landlords can access
    if request.user.profile.user_type != 'landlord':
        return redirect('home')

    # Get all properties owned by this landlord
    properties = Property.objects.filter(landlord=request.user).order_by('-created_at')

    # Get pending interests
    pending_interests = Interest.objects.filter(
        property__landlord=request.user,
        status='pending'
    ).select_related('tenant', 'property').order_by('-created_at')


    # Calculate statistics
    total_properties = properties.count()
    available_properties = properties.filter(is_available=True).count()
    occupied_properties = properties.filter(occupancy_status='occupied').count()

    # Get total earnings from inspections (20% share)
    inspection_earnings = Transaction.objects.filter(
        user=request.user,
        transaction_type='inspection_share_landlord',
        status='success'
    ).aggregate(total=Sum('amount'))['total'] or 0

    # Get pending occupancy requests
    pending_requests = OccupancyRequest.objects.filter(
        property__in=properties,
        status='pending'
    ).select_related('tenant', 'property')

    # Get pending reservations
    pending_reservations = Reservation.objects.filter(
        property__in=properties,
        status='pending'
    ).select_related('tenant', 'property')

    # Get recent transactions
    recent_transactions = Transaction.objects.filter(
        user=request.user
    ).order_by('-created_at')[:10]

    unread_count = 0
    if request.user.is_authenticated:
        unread_count = ChatMessage.objects.filter(
            recipient=request.user,
            is_read=False
        ).count()

    context = {
        'properties': properties,
        'pending_interests': pending_interests,  # Add this
        'total_properties': total_properties,
        'available_properties': available_properties,
        'occupied_properties': occupied_properties,
        'wallet_balance': request.user.profile.wallet_balance,
        'inspection_earnings': inspection_earnings,
        'pending_requests': pending_requests,
        'pending_reservations': pending_reservations,
        'recent_transactions': recent_transactions,
        'now': timezone.now(),
        'unread_messages_count': unread_count,
    }
    return render(request, 'landlord_dashboard.html', context)

    # Get expired interests (for information)
    expired_interests = Interest.objects.filter(
        property__landlord=request.user,
        status='expired'
    ).select_related('tenant', 'property')[:5]

    context['expired_interests'] = expired_interests

    # In landlord_dashboard view, add:
    active_escrows = Escrow.objects.filter(
        landlord=request.user,
        status='held'
    ).select_related('property', 'tenant')

    context['active_escrows'] = active_escrows

    # In landlord_dashboard view, add:

    # Pending occupancy requests
    pending_occupancy = OccupancyRequest.objects.filter(
        property__landlord=request.user,
        status='pending'
    ).select_related('tenant', 'property')

    # Pending reservations (already have this)
    # pending_reservations = Reservation.objects.filter(...)

    context['pending_occupancy'] = pending_occupancy
    context['pending_reservations'] = pending_reservations


from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .decorators import landlord_verified_required
from .forms import PropertyForm
from .models import Property, PropertyImage, PropertyFeature


@login_required
@landlord_verified_required
def add_property(request):
    """
    View for landlords to add a new property
    """
    # Get all features for the template
    all_features = PropertyFeature.objects.all()

    # Handle POST request
    if request.method == 'POST':
        # Create form instance with POST data and files
        form = PropertyForm(request.POST, request.FILES)

        if form.is_valid():
            try:
                # Save property but don't commit to database yet
                property = form.save(commit=False)
                property.landlord = request.user
                property.inspection_fee = 2000  # Fixed fee
                property.save()  # Now save to database

                # Save many-to-many relationships (features)
                form.save_m2m()

                # Handle multiple image uploads
                images = request.FILES.getlist('images')
                if images:
                    for index, image_file in enumerate(images):
                        PropertyImage.objects.create(
                            property=property,
                            image=image_file,
                            is_primary=(index == 0)  # First image is primary
                        )
                    messages.success(request, f'Property added successfully with {len(images)} images!')
                else:
                    messages.warning(request,
                                     'Property added successfully. You can add images later by editing the property.')

                return redirect('property_detail', property_id=property.id)

            except Exception as e:
                messages.error(request, f'Error saving property: {str(e)}')
                # Return to form with errors
                context = {
                    'form': form,
                    'all_features': all_features,
                    'editing': False,
                }
                return render(request, 'add_property.html', context)
        else:
            # Form has validation errors
            messages.error(request, 'Please correct the errors below.')
            # Return to form with errors
            context = {
                'form': form,
                'all_features': all_features,
                'editing': False,
            }
            return render(request, 'add_property.html', context)

    # Handle GET request - show empty form
    else:
        form = PropertyForm()
        context = {
            'form': form,
            'all_features': all_features,
            'editing': False,
        }
        return render(request, 'add_property.html', context)

    # Failsafe return - this should never be reached but prevents None return
    return redirect('landlord_dashboard')



@login_required
@landlord_verified_required
def edit_property(request, property_id):
    property = get_object_or_404(Property, id=property_id, landlord=request.user)

    if request.method == 'POST':
        form = PropertyForm(request.POST, request.FILES, instance=property)
        if form.is_valid():
            property = form.save()

            # Handle image deletions
            delete_ids = request.POST.getlist('delete_images')
            if delete_ids:
                deleted = PropertyImage.objects.filter(id__in=delete_ids).delete()
                messages.info(request, f'Removed {len(delete_ids)} image(s).')

            # Handle new image uploads
            new_images = request.FILES.getlist('images')
            if new_images:
                # Check if property already has any images
                has_primary = property.images.filter(is_primary=True).exists()

                for index, image_file in enumerate(new_images):
                    property_image = PropertyImage(
                        property=property,
                        image=image_file,
                        is_primary=(not has_primary and index == 0)
                    )
                    property_image.save()

                messages.success(request, f'Added {len(new_images)} new image(s).')

            messages.success(request, 'Property updated successfully!')
            return redirect('property_detail', property_id=property.id)
    else:
        form = PropertyForm(instance=property)

    return render(request, 'add_property.html', {
        'form': form,
        'property': property,
        'editing': True
    })




def landlord_can_post(user):
    """Check if landlord is verified and can post properties"""
    if not user.is_authenticated:
        return False
    if user.profile.user_type != 'landlord':
        return False
    if not user.profile.is_verified:
        return False
    return True

# In your add_property.html view:
@login_required
def add_property(request):
    if not landlord_can_post(request.user):
        messages.error(request, 'Your landlord account must be verified before you can post properties.')
        return redirect('landlord_dashboard')


@login_required
def pay_inspection_before_view(request, property_id):
    """Pay inspection fee before viewing property details"""

    # First, get the property
    property = get_object_or_404(Property, id=property_id)

    # Now we can use property for all checks

    # ===== SECURITY CHECKS =====
    # Check if user is verified
    if not request.user.profile.is_verified:
        messages.warning(request, 'You need to verify your account before inspecting properties.')
        return redirect('submit_verification')

    # Check wallet balance
    if request.user.profile.wallet_balance < property.inspection_fee:
        messages.error(request, f'Insufficient balance. You need ₦{property.inspection_fee}')
        return redirect('fund_wallet')

    # Check if email is verified
    if not request.user.profile.email_verified:
        messages.warning(request, 'Please verify your email address first.')
        return redirect('home')

    # Check if already paid and still active
    existing_inspection = Inspection.objects.filter(
        user=request.user,
        property=property
    ).order_by('-paid_at').first()

    if existing_inspection:
        if existing_inspection.access_expires_at > timezone.now():
            messages.info(request, 'You already have active access to this property.')
            return redirect('property_detail', property_id=property_id)
        else:
            # Previous inspection expired, allow re-payment
            messages.info(request, 'Your previous inspection has expired. Please pay again to renew access.')

    fee = property.inspection_fee

    if request.method == 'POST':
        # Process payment
        try:
            from django.db import transaction as db_transaction
            from decimal import Decimal
            import uuid

            with db_transaction.atomic():
                # Get system user
                system_user = User.objects.get(username='system')

                # Create reference
                main_ref = f"INSP-{uuid.uuid4().hex[:10].upper()}"

                # Deduct from tenant
                request.user.profile.wallet_balance -= fee
                request.user.profile.save()

                # Record tenant transaction
                tenant_transaction = Transaction.objects.create(
                    user=request.user,
                    amount=-fee,
                    transaction_type='inspection',
                    reference=main_ref,
                    status='success',
                    description=f"Inspection fee for {property.title}",
                    property=property
                )

                # Split fee
                landlord_share = (fee * Decimal('0.2')).quantize(Decimal('0.01'))
                system_share = (fee * Decimal('0.8')).quantize(Decimal('0.01'))

                # Credit landlord
                property.landlord.profile.wallet_balance += landlord_share
                property.landlord.profile.save()

                Transaction.objects.create(
                    user=property.landlord,
                    amount=landlord_share,
                    transaction_type='inspection_share_landlord',
                    reference=f"{main_ref}-L",
                    status='success',
                    description=f"Your share of inspection fee",
                    property=property
                )

                # Credit system
                system_user.profile.wallet_balance += system_share
                system_user.profile.save()

                Transaction.objects.create(
                    user=system_user,
                    amount=system_share,
                    transaction_type='inspection_share_system',
                    reference=f"{main_ref}-S",
                    status='success',
                    description=f"Platform share",
                    property=property
                )

                # Create NEW inspection record
                inspection = Inspection.objects.create(
                    user=request.user,
                    property=property,
                    amount_paid=fee,
                    transaction=tenant_transaction,
                    access_expires_at=timezone.now() + timedelta(hours=24)
                )

                messages.success(request, 'Payment successful! You now have 24-hour access to full property details.')
                return redirect('property_detail', property_id=property.id)

        except User.DoesNotExist:
            messages.error(request, 'System configuration error. Please contact support.')
            return redirect('pay_inspection_before_view', property_id=property.id)

        except Exception as e:
            messages.error(request, f'Payment failed: {str(e)}')
            return redirect('pay_inspection_before_view', property_id=property.id)

    # GET request - show payment page
    context = {
        'property': property,
        'fee': fee,
        'current_balance': request.user.profile.wallet_balance,
        'new_balance': request.user.profile.wallet_balance - fee,
        'is_renewal': existing_inspection is not None,
    }

    return render(request, 'pay_inspection_before.html', context)





@login_required
@tenant_verified_required
def request_occupancy(request, property_id):
    """Request to occupy property (after deposit and offline rent payment)"""
    property = get_object_or_404(Property, id=property_id)

    # Check if escrow exists
    try:
        escrow = Escrow.objects.get(
            tenant=request.user,
            property=property,
            escrow_type='occupancy',
            status='held'
        )
    except Escrow.DoesNotExist:
        messages.error(request, 'You must pay the deposit first.')
        return redirect('pay_deposit', property_id=property_id)

    # Check if already requested
    if OccupancyRequest.objects.filter(tenant=request.user, property=property).exists():
        messages.info(request, 'You have already requested occupancy.')
        return redirect('property_detail', property_id=property_id)

    if request.method == 'POST':
        # Create occupancy request
        occupancy_request = OccupancyRequest.objects.create(
            tenant=request.user,
            property=property,
            status='pending',
            tenant_full_name=request.user.profile.full_name_on_id or request.user.username,
            tenant_occupation=request.user.profile.occupation or '',
            tenant_marital_status=request.user.profile.marital_status or '',
            tenant_religion=request.user.profile.religion or '',
            tenant_state_of_origin=request.user.profile.state_of_origin or '',
            tenant_phone=request.user.profile.phone or '',
            tenant_email=request.user.email
        )

        messages.success(request, 'Occupancy request sent to landlord. They will verify your offline rent payment.')
        return redirect('property_detail', property_id=property_id)

    context = {
        'property': property,
        'escrow': escrow,
    }
    return render(request, 'request_occupancy.html', context)





@login_required
def approve_occupancy_change(request, property_id, decision):
    property = get_object_or_404(Property, id=property_id, landlord=request.user)
    if decision == 'approve':
        property.occupancy_status = property.pending_occupancy_change
        property.pending_occupancy_change = None
        property.save()
        messages.success(request, 'Occupancy updated.')
    elif decision == 'reject':
        property.pending_occupancy_change = None
        property.save()
        messages.success(request, 'Change rejected.')
    return redirect('landlord_dashboard')





# Add this to the Property model or as a separate utility function

def can_tenant_request_occupancy(tenant, property):
    """Check if tenant can request occupancy (must have signed agreement and be verified)"""
    if not tenant.profile.is_verified:
        return False, "Your account must be verified before you can occupy a property."

    if not SignedAgreement.objects.filter(tenant=tenant, property=property).exists():
        return False, "You must sign the rental agreement first."

    return True, "OK"


def can_tenant_request_reservation(tenant, property):
    """Check if tenant can request reservation (must have signed agreement and be verified)"""
    if not tenant.profile.is_verified:
        return False, "Your account must be verified before you can reserve a property."

    if not SignedAgreement.objects.filter(tenant=tenant, property=property).exists():
        return False, "You must sign the rental agreement first."

    return True, "OK"


from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Transaction
import uuid


@login_required
def fund_wallet(request):
    """Page to fund wallet"""
    if request.method == 'POST':
        amount = request.POST.get('amount')

        try:
            amount = float(amount)
            if amount <= 0:
                messages.error(request, 'Please enter an amount greater than 0.')
                return redirect('fund_wallet')
        except (ValueError, TypeError):
            messages.error(request, 'Please enter a valid amount.')
            return redirect('fund_wallet')

        # Generate unique reference
        reference = f"FUND-{uuid.uuid4().hex[:10].upper()}"

        # Create transaction record
        transaction = Transaction.objects.create(
            user=request.user,
            amount=amount,
            transaction_type='deposit',
            reference=reference,
            status='pending',
            description=f'Wallet funding of ₦{amount}'
        )

        # Here you would integrate with Paystack
        # For now, simulate successful payment
        transaction.status = 'success'
        transaction.save()

        # Update wallet balance
        request.user.profile.wallet_balance += amount
        request.user.profile.save()

        messages.success(request, f'Successfully added ₦{amount} to your wallet!')
        return redirect('tenant_dashboard')

    # Get recent transactions
    recent_transactions = Transaction.objects.filter(
        user=request.user,
        transaction_type='deposit'
    ).order_by('-created_at')[:5]

    context = {
        'recent_transactions': recent_transactions,
        'wallet_balance': request.user.profile.wallet_balance,
    }
    return render(request, 'fund_wallet.html', context)

def payment_callback(request):
    reference = request.GET.get('reference')
    if not reference:
        messages.error(request, 'No reference')
        return redirect('home')

    headers = {'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}'}
    response = requests.get(f'https://api.paystack.co/transaction/verify/{reference}', headers=headers)
    if response.status_code == 200:
        data = response.json()['data']
        if data['status'] == 'success':
            try:
                transaction = Transaction.objects.get(reference=reference)
                transaction.status = 'success'
                transaction.save()
                # Update user balance
                profile = transaction.user.profile
                profile.balance += transaction.amount
                profile.save()
                messages.success(request, 'Wallet funded successfully.')
            except Transaction.DoesNotExist:
                messages.error(request, 'Transaction not found.')
        else:
            messages.error(request, 'Payment failed.')
    else:
        messages.error(request, 'Verification failed.')
    return redirect('tenant_dashboard')


# core/views.py
from django.db import transaction as db_transaction


@db_transaction.atomic
def process_inspection_payment(request, property, fee):
    """Process the actual payment with fee splitting"""
    from .models import Transaction, Inspection, User

    # Get system user
    try:
        system_user = User.objects.get(username='system')
    except User.DoesNotExist:
        messages.error(request, 'System configuration error. Please contact support.')
        return redirect('property_detail', property_id=property.id)

    # Create main transaction reference
    main_ref = f"INSP-{uuid.uuid4().hex[:10].upper()}"

    # Deduct from tenant wallet
    tenant_profile = request.user.profile
    tenant_profile.wallet_balance -= fee
    tenant_profile.save()

    # Record tenant's payment transaction
    tenant_transaction = Transaction.objects.create(
        user=request.user,
        amount=-fee,
        transaction_type='inspection',
        reference=main_ref,
        status='success',
        description=f"Inspection fee for {property.title}",
        property=property,
        landlord=property.landlord
    )

    landlord_share = round(fee * Decimal('0.2'), 2)
    system_share = round(fee * Decimal('0.8'), 2)

    # Credit landlord (20%)
    landlord_profile = property.landlord.profile
    landlord_profile.wallet_balance += landlord_share
    landlord_profile.save()

    Transaction.objects.create(
        user=property.landlord,
        amount=landlord_share,
        transaction_type='inspection_share_landlord',
        reference=f"{main_ref}-L",
        status='success',
        description=f"Your 20% share of inspection fee for {property.title}",
        property=property
    )

    # Credit system (80%)
    system_profile = system_user.profile
    system_profile.wallet_balance += system_share
    system_profile.save()

    Transaction.objects.create(
        user=system_user,
        amount=system_share,
        transaction_type='inspection_share_system',
        reference=f"{main_ref}-S",
        status='success',
        description=f"Platform 80% share of inspection fee for {property.title}",
        property=property
    )

    # Create inspection record
    inspection = Inspection.objects.create(
        user=request.user,
        property=property,
        amount_paid=fee,
        transaction=tenant_transaction
    )

    messages.success(
        request,
        f'Inspection paid successfully! You now have access to full property details for 24 hours.'
    )

    return redirect('property_detail', property_id=property.id)


@login_required
def pay_inspection(request, property_id):
    property = get_object_or_404(Property, id=property_id)
    # Check if already paid
    if Inspection.objects.filter(user=request.user, property=property).exists():
        messages.info(request, 'You already have access to this property.')
        return redirect('property_detail', property_id=property_id)

    fee = property.inspection_fee
    if request.user.profile.balance >= fee:
        # Deduct
        request.user.profile.balance -= fee
        request.user.profile.save()
        # Record inspection
        Inspection.objects.create(user=request.user, property=property)
        # Create transaction
        Transaction.objects.create(
            user=request.user,
            amount=fee,
            transaction_type='inspection',
            reference=f"insp-{uuid.uuid4()}",
            status='success',
            property=property
        )
        messages.success(request, 'Inspection paid. You can now view full details.')
    else:
        messages.error(request, f'Insufficient balance. Please fund your wallet (fee: {fee})')
        return redirect('fund_wallet')
    return redirect('property_detail', property_id=property_id)


def property_detail(request, property_id):
    property = get_object_or_404(Property, id=property_id)

    # Check if user has paid for inspection
    has_paid = False
    inspection = None

    if request.user.is_authenticated:
        if request.user == property.landlord:
            has_paid = True
        else:
            inspections = Inspection.objects.filter(
                user=request.user,
                property=property
            ).order_by('-paid_at')

            if inspections.exists():
                inspection = inspections.first()
                if inspection.access_expires_at > timezone.now():
                    has_paid = True
                else:
                    inspection = None

    # Calculate deposit amount
    annual_rent = property.price * Decimal('12')
    deposit_amount = annual_rent * Decimal('0.2')

    # Get featured property (most recent available property)
    featured_property = Property.objects.filter(
        is_available=True
    ).exclude(id=property.id).order_by('-created_at').first()

    # Get recently added properties
    recent_properties = Property.objects.filter(
        is_available=True
    ).exclude(id=property.id).order_by('-created_at')[:3]

    # Get related properties (same city or similar price range)
    related_properties = Property.objects.filter(
        is_available=True,
        city=property.city
    ).exclude(id=property.id)[:4]

    context = {
        'property': property,
        'has_paid': has_paid,
        'inspection': inspection,
        'deposit_amount': deposit_amount,
        'annual_rent': annual_rent,
        'featured_property': featured_property,
        'recent_properties': recent_properties,
        'related_properties': related_properties,
    }

    return render(request, 'property_detail.html', context)



def tenant_required(view_func):
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated and request.user.profile.user_type == 'tenant':
            return view_func(request, *args, **kwargs)
        raise PermissionDenied
    return wrapper



def landlord_required(view_func):
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated and request.user.profile.user_type == 'landlord':
            return view_func(request, *args, **kwargs)
        raise PermissionDenied
    return wrapper


# homigram/views.py


def register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Send verification email
            send_verification_email(request, user)

            messages.success(request,
                             'Registration successful! Please check your email to verify your account.')
            return redirect('login')
    else:
        form = UserRegistrationForm()

    return render(request, 'register.html', {'form': form})


from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.contrib.auth import get_user_model

User = get_user_model()


def verify_email(request, uidb64, token):
    """Verify user's email address"""
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    from .utils import account_activation_token

    if user is not None and account_activation_token.check_token(user, token):
        # Activate user
        user.is_active = True
        user.save()

        # Mark email as verified in profile
        user.profile.email_verified = True
        user.profile.save()

        messages.success(request, 'Your email has been verified! You can now log in.')
        return redirect('login')
    else:
        messages.error(request, 'The verification link is invalid or has expired.')
        return redirect('home')

# core/views.py

@login_required
def submit_verification(request):
    profile = request.user.profile

    # Check if already verified
    if profile.is_verified:
        messages.info(request, 'Your account is already verified.')
        # Redirect to appropriate dashboard
        if profile.user_type == 'tenant':
            return redirect('tenant_dashboard')
        else:
            return redirect('landlord_dashboard')

    # Check if verification is pending
    if profile.verification_submitted_at and not profile.is_verified:
        messages.warning(request, 'Your verification is still pending review. Please wait for admin approval.')
        if profile.user_type == 'tenant':
            return redirect('tenant_dashboard')
        else:
            return redirect('landlord_dashboard')

    if request.method == 'POST':
        form = VerificationSubmissionForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.verification_submitted_at = timezone.now()
            profile.save()

            messages.success(request,
                             'Verification documents submitted successfully! An admin will review your application soon.')
            if profile.user_type == 'tenant':
                return redirect('tenant_dashboard')
            else:
                return redirect('landlord_dashboard')
    else:
        form = VerificationSubmissionForm(instance=profile)

    return render(request, 'submit_verification.html', {'form': form})


@login_required
@tenant_verified_required
def view_agreement(request, property_id):
    """View the rental agreement before signing"""
    property = get_object_or_404(Property, id=property_id)

    # Check if already signed
    existing_agreement = SignedAgreement.objects.filter(
        tenant=request.user,
        property=property
    ).first()

    if existing_agreement:
        messages.info(request, 'You have already signed the agreement for this property.')
        return redirect('property_detail', property_id=property_id)

    # Check if landlord uploaded agreement
    if not property.rental_agreement:
        messages.error(request, 'The landlord has not uploaded a rental agreement yet.')
        return redirect('property_detail', property_id=property_id)

    context = {
        'property': property,
        'agreement_url': property.rental_agreement.url,
    }
    return render(request, 'view_agreement.html', context)


@login_required
@tenant_verified_required
def sign_agreement(request, property_id):
    """Handle the actual signing"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    property = get_object_or_404(Property, id=property_id)

    # Check if already signed
    if SignedAgreement.objects.filter(tenant=request.user, property=property).exists():
        return JsonResponse({'error': 'Already signed'}, status=400)

    # Get signature data from POST
    data = json.loads(request.body)
    signature_data = data.get('signature')

    if not signature_data:
        return JsonResponse({'error': 'Signature is required'}, status=400)

    # Create the signed agreement record
    agreement = SignedAgreement.objects.create(
        tenant=request.user,
        property=property,
        signature_data=signature_data,
        ip_address=request.META.get('REMOTE_ADDR')
    )

    # Generate PDF of signed agreement
    pdf_file = generate_signed_agreement_pdf(agreement)
    agreement.agreement_file.save(f'agreement_{agreement.id}.pdf', pdf_file)

    return JsonResponse({
        'success': True,
        'message': 'Agreement signed successfully',
        'redirect_url': reverse('property_detail', args=[property_id])
    })


def generate_signed_agreement_pdf(agreement):
    """Generate a PDF of the signed agreement"""
    from django.core.files.base import ContentFile
    import io

    # Render HTML template for PDF
    html_string = render_to_string('agreement_pdf.html', {
        'agreement': agreement,
        'tenant': agreement.tenant,
        'property': agreement.property,
        'landlord': agreement.property.landlord,
        'signed_date': agreement.signed_at,
    })

    # Generate PDF
    pdf_file = HTML(string=html_string).write_pdf()

    # Return as Django ContentFile
    return ContentFile(pdf_file)


# core/views.py
from django.db.models import Q


def property_list(request):
    properties = Property.objects.filter(is_available=True)

    # Search by location (city or state)
    location = request.GET.get('location')
    if location:
        properties = properties.filter(
            Q(city__icontains=location) |
            Q(state__icontains=location) |
            Q(address__icontains=location)
        )

    # Filter by price range
    min_price = request.GET.get('min_price')
    if min_price:
        properties = properties.filter(price__gte=min_price)

    max_price = request.GET.get('max_price')
    if max_price:
        properties = properties.filter(price__lte=max_price)

    # Filter by bedrooms
    bedrooms = request.GET.get('bedrooms')
    if bedrooms:
        properties = properties.filter(bedrooms__gte=bedrooms)

    # Filter by property features
    feature_ids = request.GET.getlist('features')
    if feature_ids:
        properties = properties.filter(features__id__in=feature_ids).distinct()

    # Sorting
    sort_by = request.GET.get('sort', '-created_at')  # Default: newest first
    if sort_by in ['price', '-price', 'created_at', '-created_at', 'bedrooms', '-bedrooms']:
        properties = properties.order_by(sort_by)

    # Get all features for filter sidebar
    all_features = PropertyFeature.objects.all()

    # Get min and max prices for range sliders
    price_stats = properties.aggregate(
        min_price=models.Min('price'),
        max_price=models.Max('price')
    )

    context = {
        'properties': properties,
        'all_features': all_features,
        'total_count': properties.count(),
        'min_price': price_stats['min_price'] or 0,
        'max_price': price_stats['max_price'] or 1000000,
        'selected_features': [int(id) for id in feature_ids],
        'current_sort': sort_by,
        'search_params': request.GET.urlencode(),
    }

    return render(request, 'property_list.html', context)
    # Pagination
    paginator = Paginator(properties, 12)  # Show 12 properties per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'properties': page_obj,  # Use page_obj instead of properties
        'all_features': all_features,
        'total_count': paginator.count,
        # ... rest of context
    }

    return render(request, 'property_list.html', context)


@login_required
def fund_wallet(request):
    """Page to fund wallet via Paystack"""
    if request.method == 'POST':
        amount = request.POST.get('amount')

        try:
            amount = float(amount)
            if amount <= 0:
                messages.error(request, 'Please enter an amount greater than 0.')
                return redirect('fund_wallet')
        except (ValueError, TypeError):
            messages.error(request, 'Please enter a valid amount.')
            return redirect('fund_wallet')

        # Generate unique reference
        reference = f"FUND-{uuid.uuid4().hex[:10].upper()}"

        # Create transaction record
        transaction = Transaction.objects.create(
            user=request.user,
            amount=amount,
            transaction_type='deposit',
            reference=reference,
            status='pending',
            description=f'Wallet funding of ₦{amount}'
        )

        # Initialize Paystack transaction
        headers = {
            'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}',
            'Content-Type': 'application/json',
        }

        data = {
            'email': request.user.email,
            'amount': int(amount * 100),  # Paystack uses kobo (multiply by 100)
            'reference': reference,
            'callback_url': request.build_absolute_uri('/payment/callback/'),
        }

        try:
            response = requests.post(
                'https://api.paystack.co/transaction/initialize',
                json=data,
                headers=headers
            )

            if response.status_code == 200:
                result = response.json()
                if result['status']:
                    # Redirect to Paystack payment page
                    return redirect(result['data']['authorization_url'])
                else:
                    messages.error(request, 'Payment initialization failed. Please try again.')
                    transaction.status = 'failed'
                    transaction.save()
            else:
                messages.error(request, 'Could not connect to payment gateway. Please try again.')
                transaction.status = 'failed'
                transaction.save()

        except requests.exceptions.RequestException:
            messages.error(request, 'Network error. Please try again.')
            transaction.status = 'failed'
            transaction.save()

        return redirect('fund_wallet')

    # Get recent transactions
    recent_transactions = Transaction.objects.filter(
        user=request.user,
        transaction_type='deposit'
    ).order_by('-created_at')[:5]

    context = {
        'recent_transactions': recent_transactions,
        'current_balance': request.user.profile.wallet_balance,
        'paystack_public_key': settings.PAYSTACK_PUBLIC_KEY,
    }
    return render(request, 'fund_wallet.html', context)


@login_required
def payment_callback(request):
    """Handle Paystack payment callback"""
    reference = request.GET.get('reference')

    if not reference:
        messages.error(request, 'No payment reference found.')
        return redirect('fund_wallet')

    # Verify transaction with Paystack
    headers = {
        'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}',
    }

    try:
        response = requests.get(
            f'https://api.paystack.co/transaction/verify/{reference}',
            headers=headers
        )

        if response.status_code == 200:
            result = response.json()

            if result['status'] and result['data']['status'] == 'success':
                # Find the transaction
                try:
                    transaction = Transaction.objects.get(reference=reference)
                    transaction.status = 'success'
                    transaction.save()

                    # Update user's wallet balance
                    profile = request.user.profile
                    profile.wallet_balance += transaction.amount
                    profile.save()

                    messages.success(request, f'Successfully added ₦{transaction.amount} to your wallet!')
                except Transaction.DoesNotExist:
                    messages.error(request, 'Transaction record not found.')
            else:
                messages.error(request, 'Payment verification failed.')
        else:
            messages.error(request, 'Could not verify payment.')

    except requests.exceptions.RequestException:
        messages.error(request, 'Network error during verification.')

    return redirect('fund_wallet')


@login_required
@tenant_verified_required
def express_interest(request, property_id):
    """Tenant expresses interest in a property"""
    from datetime import timedelta
    from django.utils import timezone

    print(f"\n{'=' * 50}")
    print(f"EXPRESS INTEREST VIEW")
    print(f"Property ID: {property_id}")
    print(f"User: {request.user.username}")

    property = get_object_or_404(Property, id=property_id)
    print(f"Property: {property.title}")

    # Check if tenant has inspected the property (using most recent inspection)
    inspections = Inspection.objects.filter(
        user=request.user,
        property=property
    ).order_by('-paid_at')  # Most recent first

    if not inspections.exists():
        print("❌ No inspection found")
        messages.error(request, 'You must inspect this property first before expressing interest.')
        return redirect('property_detail', property_id=property_id)

    # Get the most recent inspection
    inspection = inspections.first()
    print(f"✅ Found inspection from {inspection.paid_at}")
    print(f"   Access expires: {inspection.access_expires_at}")
    print(f"   Current time: {timezone.now()}")

    # Check if inspection is still valid
    if inspection.access_expires_at < timezone.now():
        print("❌ Inspection has expired")
        messages.error(request, 'Your inspection access has expired. Please pay for inspection again.')
        return redirect('pay_inspection_before_view', property_id=property_id)

    print("✅ Inspection is valid")

    # Check if already expressed interest
    existing_interest = Interest.objects.filter(
        tenant=request.user,
        property=property
    ).first()

    if existing_interest:
        print(f"Existing interest found: {existing_interest.status}")
        if existing_interest.status == 'pending':
            messages.info(request, 'You have already expressed interest. Waiting for landlord response.')
        elif existing_interest.status == 'approved':
            messages.info(request, 'Your interest was approved! You have extended access for 7 days.')
        elif existing_interest.status == 'rejected':
            messages.error(request, 'Your interest was rejected by the landlord.')
        return redirect('property_detail', property_id=property_id)

    if request.method == 'POST':
        # Create interest record
        interest = Interest.objects.create(
            tenant=request.user,
            property=property,
            status='pending',
            expires_at=timezone.now() + timedelta(days=7)
        )

        print(f"✅ Interest created with ID: {interest.id}")
        print(f"   Expires: {interest.expires_at}")

        messages.success(request, 'Interest expressed! The landlord will review your profile within 7 days.')
        return redirect('property_detail', property_id=property_id)

    # GET request - show confirmation page
    print("📄 Rendering express interest template")
    print(f"{'=' * 50}\n")

    context = {
        'property': property,
        'inspection': inspection,
    }
    return render(request, 'express_interest.html', context)




# ============================================
# OCCUPANCY VIEWS
# ============================================

@login_required
@tenant_verified_required
def request_occupancy(request, property_id):
    """Request to occupy property (after deposit and offline rent payment)"""
    property = get_object_or_404(Property, id=property_id)

    # Check if escrow exists
    try:
        escrow = Escrow.objects.get(
            tenant=request.user,
            property=property,
            escrow_type='occupancy',
            status='held'
        )
    except Escrow.DoesNotExist:
        messages.error(request, 'You must pay the deposit first.')
        return redirect('pay_deposit', property_id=property_id)

    # Check if already requested
    existing_request = OccupancyRequest.objects.filter(
        tenant=request.user,
        property=property
    ).first()

    if existing_request:
        if existing_request.status == 'pending':
            messages.info(request, 'You already have a pending occupancy request.')
        elif existing_request.status == 'approved':
            messages.info(request, 'Your occupancy request was already approved.')
        else:
            messages.info(request, f'Your previous request was {existing_request.status}.')
        return redirect('property_detail', property_id=property_id)

    if request.method == 'POST':
        # Create occupancy request
        occupancy_request = OccupancyRequest.objects.create(
            tenant=request.user,
            property=property,
            status='pending',
            tenant_full_name=request.user.profile.full_name_on_id or request.user.username,
            tenant_occupation=request.user.profile.occupation or '',
            tenant_marital_status=request.user.profile.marital_status or '',
            tenant_religion=request.user.profile.religion or '',
            tenant_state_of_origin=request.user.profile.state_of_origin or '',
            tenant_phone=request.user.profile.phone or '',
            tenant_email=request.user.email
        )

        messages.success(request, 'Occupancy request sent to landlord. They will verify your offline rent payment.')
        return redirect('property_detail', property_id=property_id)

    context = {
        'property': property,
        'escrow': escrow,
    }
    return render(request, 'request_occupancy.html', context)


@login_required
@landlord_verified_required
def manage_occupancy(request, request_id):
    """Landlord approves/rejects occupancy request"""
    occupancy_request = get_object_or_404(OccupancyRequest, id=request_id, property__landlord=request.user)
    property = occupancy_request.property

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'approve':
            # Get the escrow
            try:
                escrow = Escrow.objects.get(
                    tenant=occupancy_request.tenant,
                    property=property,
                    escrow_type='occupancy'
                )
                # Mark that offline rent was paid
                escrow.offline_rent_paid = True
                escrow.save()
            except Escrow.DoesNotExist:
                messages.error(request, 'Escrow record not found.')
                return redirect('landlord_dashboard')

            # Update occupancy request
            occupancy_request.status = 'approved'
            occupancy_request.reviewed_at = timezone.now()
            occupancy_request.save()

            # Update property status
            property.occupancy_status = 'occupied'
            property.reservation_status = 'occupied'
            property.save()

            messages.success(request,
                             f'Occupancy approved for {occupancy_request.tenant.username}. They can now move in.')

        elif action == 'reject':
            occupancy_request.status = 'rejected'
            occupancy_request.reviewed_at = timezone.now()
            occupancy_request.save()

            messages.info(request, f'Occupancy rejected for {occupancy_request.tenant.username}')

        return redirect('landlord_dashboard')

    context = {
        'request': occupancy_request,
        'tenant': occupancy_request.tenant,
        'property': property,
    }
    return render(request, 'manage_occupancy.html', context)


# ============================================
# RESERVATION VIEWS
# ============================================

@login_required
@tenant_verified_required
def request_reservation(request, property_id):
    """Request to reserve property (after deposit)"""
    property = get_object_or_404(Property, id=property_id)

    # Check if escrow exists
    try:
        escrow = Escrow.objects.get(
            tenant=request.user,
            property=property,
            escrow_type='reservation',
            status='held'
        )
    except Escrow.DoesNotExist:
        messages.error(request, 'You must pay the deposit first.')
        return redirect('pay_deposit', property_id=property_id)

    # Check if property is available for reservation
    if property.reservation_status != 'available':
        messages.error(request, 'This property is not available for reservation.')
        return redirect('property_detail', property_id=property_id)

    # Check if already reserved
    existing = Reservation.objects.filter(
        tenant=request.user,
        property=property
    ).first()

    if existing:
        if existing.status == 'pending':
            messages.info(request, 'You already have a pending reservation request.')
        elif existing.status == 'active':
            messages.info(request, 'You already have an active reservation for this property.')
        return redirect('reservation_detail', reservation_id=existing.id)

    daily_fee = property.daily_reservation_fee

    if request.method == 'POST':
        # Create reservation
        reservation = Reservation.objects.create(
            tenant=request.user,
            property=property,
            daily_fee=daily_fee,
            status='pending'
        )

        messages.success(request, 'Reservation request sent to landlord!')
        return redirect('reservation_detail', reservation_id=reservation.id)

    context = {
        'property': property,
        'escrow': escrow,
        'daily_fee': daily_fee,
    }
    return render(request, 'request_reservation.html', context)


@login_required
@landlord_verified_required
def manage_reservation(request, reservation_id):
    """Landlord approves/rejects reservation request"""
    reservation = get_object_or_404(Reservation, id=reservation_id, property__landlord=request.user)
    property = reservation.property

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'approve':
            # Check if property still available
            if property.reservation_status != 'available':
                messages.error(request, 'This property is no longer available for reservation.')
                return redirect('landlord_dashboard')

            # Approve reservation
            reservation.status = 'active'
            reservation.approved_by_landlord = True
            reservation.approved_at = timezone.now()
            reservation.start_date = timezone.now()
            reservation.save()

            # Update property status
            property.reservation_status = 'reserved'
            property.save()

            messages.success(request,
                             f'Reservation approved for {reservation.tenant.username}. Daily fees will now be charged.')

        elif action == 'reject':
            reservation.status = 'cancelled_by_landlord'
            reservation.actual_end_date = timezone.now()
            reservation.save()

            messages.info(request, f'Reservation rejected for {reservation.tenant.username}')

        return redirect('landlord_dashboard')

    context = {
        'reservation': reservation,
        'tenant': reservation.tenant,
        'property': property,
    }
    return render(request, 'manage_reservation.html', context)


@login_required
def reservation_detail(request, reservation_id):
    """View reservation details"""
    reservation = get_object_or_404(Reservation, id=reservation_id)

    # Check permission
    if request.user not in [reservation.tenant, reservation.property.landlord]:
        messages.error(request, 'You do not have permission to view this reservation.')
        return redirect('home')

    # Calculate days reserved
    days_reserved = 0
    if reservation.start_date:
        days_reserved = (timezone.now() - reservation.start_date).days

    # Get escrow info
    escrow = Escrow.objects.filter(
        tenant=reservation.tenant,
        property=reservation.property,
        escrow_type='reservation'
    ).first()

    context = {
        'reservation': reservation,
        'is_tenant': request.user == reservation.tenant,
        'is_landlord': request.user == reservation.property.landlord,
        'daily_fee': reservation.daily_fee,
        'total_charged': reservation.total_charged,
        'days_reserved': days_reserved,
        'escrow': escrow,
        'remaining_balance': request.user.profile.wallet_balance if request.user == reservation.tenant else None,
    }
    return render(request, 'reservation_detail.html', context)


@login_required
def cancel_reservation(request, reservation_id):
    """Cancel a reservation"""
    reservation = get_object_or_404(Reservation, id=reservation_id)

    # Check permission
    if request.user == reservation.tenant:
        reservation.status = 'cancelled_by_tenant'
        reservation.actual_end_date = timezone.now()
        reservation.save()

        # Make property available again
        property = reservation.property
        property.reservation_status = 'available'
        property.save()

        messages.success(request, 'Your reservation has been cancelled.')

    elif request.user == reservation.property.landlord:
        reservation.status = 'cancelled_by_landlord'
        reservation.actual_end_date = timezone.now()
        reservation.save()

        # Make property available again
        property = reservation.property
        property.reservation_status = 'available'
        property.save()

        messages.success(request, 'Reservation cancelled.')
    else:
        messages.error(request, 'You do not have permission to cancel this reservation.')
        return redirect('home')

    return redirect('reservation_detail', reservation_id=reservation.id)

# core/views.py
@login_required
@landlord_verified_required
def manage_interest(request, interest_id):
    """Landlord approves or rejects tenant interest"""
    interest = get_object_or_404(Interest, id=interest_id, property__landlord=request.user)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'approve':
            interest.approve()  # This method should update status and extend access
            messages.success(request,
                             f'Interest approved for {interest.tenant.username}. They now have 7 days extended access.')

        elif action == 'reject':
            interest.reject()
            messages.info(request, f'Interest rejected for {interest.tenant.username}.')

        return redirect('landlord_dashboard')

    # Show tenant profile details
    context = {
        'interest': interest,
        'tenant': interest.tenant,
        'tenant_profile': interest.tenant.profile,
        'property': interest.property,
    }
    return render(request, 'manage_interest.html', context)

    # Add to manage_interest view after approval/rejection

    def send_interest_notification(interest, action):
        """Send email notification to tenant"""
        subject = f"Interest {action}d for {interest.property.title}"

        if action == 'approve':
            message = f"""
            Dear {interest.tenant.username},

            Good news! Your interest in {interest.property.title} has been APPROVED.

            You now have 7 days extended access to the property. You can now:
            - Sign the rental agreement
            - Pay the deposit (20% of rent)
            - Reserve the property

            Visit the property page to continue: 
            http://127.0.0.1:8000/property/{interest.property.id}/

            Thank you for using our platform!
            """
        else:
            message = f"""
            Dear {interest.tenant.username},

            Your interest in {interest.property.title} has been REJECTED by the landlord.

            You can still browse other available properties on our platform.

            Thank you for using our platform!
            """

        # Send email (configure email settings first)
        # send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [interest.tenant.email])


@login_required
def cancel_interest(request, interest_id):
    """Tenant cancels their interest"""
    interest = get_object_or_404(Interest, id=interest_id, tenant=request.user)

    if interest.status == 'pending':
        interest.status = 'rejected'  # Tenant cancelled
        interest.responded_at = timezone.now()
        interest.save()
        messages.success(request, 'Interest cancelled.')
    else:
        messages.error(request, 'Cannot cancel interest at this stage.')

    return redirect('property_detail', property_id=interest.property.id)


# core/views.py

@login_required
@tenant_verified_required
def pay_deposit(request, property_id):
    """Pay 20% of annual rent as deposit before occupying or reserving"""
    property = get_object_or_404(Property, id=property_id)

    # Check if interest is approved
    try:
        interest = Interest.objects.get(
            tenant=request.user,
            property=property,
            status='approved'
        )
    except Interest.DoesNotExist:
        messages.error(request, 'Your interest must be approved by the landlord first.')
        return redirect('property_detail', property_id=property_id)

    # Check if escrow already exists
    if Escrow.objects.filter(interest=interest).exists():
        messages.info(request, 'You have already paid the deposit for this property.')
        return redirect('escrow_detail', property_id=property_id)

    # Calculate annual rent and deposit (20% of annual)
    monthly_rent = property.price
    annual_rent = monthly_rent * 12
    deposit_amount = annual_rent * Decimal('0.2')  # 20% of annual rent

    # Check wallet balance
    if request.user.profile.wallet_balance < deposit_amount:
        messages.error(
            request,
            f'Insufficient balance. You need ₦{deposit_amount} for deposit. '
            f'Your balance: ₦{request.user.profile.wallet_balance}'
        )
        return redirect('fund_wallet')

    if request.method == 'POST':
        escrow_type = request.POST.get('escrow_type')  # 'occupancy' or 'reservation'

        if escrow_type not in ['occupancy', 'reservation']:
            messages.error(request, 'Invalid escrow type.')
            return redirect('pay_deposit', property_id=property_id)

        # Process payment
        from django.db import transaction as db_transaction
        from decimal import Decimal

        with db_transaction.atomic():
            # Deduct from tenant
            request.user.profile.wallet_balance -= deposit_amount
            request.user.profile.save()

            # Create escrow
            escrow = Escrow.objects.create(
                tenant=request.user,
                landlord=property.landlord,
                property=property,
                interest=interest,
                escrow_type=escrow_type,
                amount=deposit_amount,
                annual_rent=annual_rent,
                status='held'
            )

            # Create transaction
            Transaction.objects.create(
                user=request.user,
                amount=-deposit_amount,
                transaction_type='rent_deposit',
                reference=f"DEP-{escrow.id}-{timezone.now().strftime('%Y%m%d%H%M%S')}",
                status='success',
                description=f'{escrow_type.title()} deposit for {property.title}',
                property=property
            )

        messages.success(request, f'Deposit paid successfully! You can now request to {escrow_type} the property.')

        if escrow_type == 'occupancy':
            return redirect('request_occupancy', property_id=property_id)
        else:
            return redirect('request_reservation', property_id=property_id)

    # GET request - show payment page with options
    context = {
        'property': property,
        'monthly_rent': monthly_rent,
        'annual_rent': annual_rent,
        'deposit_amount': deposit_amount,
        'current_balance': request.user.profile.wallet_balance,
        'new_balance': request.user.profile.wallet_balance - deposit_amount,
    }
    return render(request, 'pay_deposit.html', context)


@db_transaction.atomic
def process_deposit_payment(request, property, interest, deposit_amount):
    """Process the actual deposit payment"""

    # Deduct from tenant wallet
    tenant_profile = request.user.profile
    tenant_profile.wallet_balance -= deposit_amount
    tenant_profile.save()

    # Create escrow record
    escrow = Escrow.objects.create(
        tenant=request.user,
        landlord=property.landlord,
        property=property,
        interest=interest,
        amount=deposit_amount,
        total_rent=property.price,
        status='held'
    )

    # Create transaction record
    Transaction.objects.create(
        user=request.user,
        amount=-deposit_amount,  # Negative for deduction
        transaction_type='rent_deposit',
        reference=f"DEP-{escrow.id}-{timezone.now().strftime('%Y%m%d%H%M%S')}",
        status='success',
        description=f'Rent deposit for {property.title} (held in escrow)',
        property=property
    )

    messages.success(
        request,
        f'Deposit of ₦{deposit_amount} paid successfully! The money is held in escrow until you move in.'
    )

    return redirect('escrow_detail', property_id=property.id)


@login_required
def escrow_detail(request, property_id):
    """View escrow details for a property"""
    property = get_object_or_404(Property, id=property_id)

    # Get the escrow for this property and the current user
    try:
        if request.user.profile.user_type == 'tenant':
            escrow = Escrow.objects.get(property=property, tenant=request.user)
        else:  # landlord
            escrow = Escrow.objects.get(property=property, landlord=request.user)
    except Escrow.DoesNotExist:
        messages.error(request, 'No escrow found for this property.')
        return redirect('property_detail', property_id=property_id)

    # Check if user is either tenant or landlord
    if request.user != escrow.tenant and request.user != escrow.landlord:
        messages.error(request, 'You do not have permission to view this escrow.')
        return redirect('home')

    context = {
        'escrow': escrow,
        'property': property,
        'is_tenant': request.user == escrow.tenant,
        'is_landlord': request.user == escrow.landlord,
    }
    return render(request, 'escrow_detail.html', context)

@login_required
def approve_escrow_release(request, escrow_id):
    """Tenant or landlord approves escrow release"""
    escrow = get_object_or_404(Escrow, id=escrow_id)

    # Check permissions
    if request.user == escrow.tenant:
        escrow.tenant_approved = True
        messages.success(request, 'You have approved releasing the deposit to the landlord.')
    elif request.user == escrow.landlord:
        escrow.landlord_approved = True
        messages.success(request, 'You have approved releasing the deposit to the tenant.')
    else:
        messages.error(request, 'You do not have permission to approve this escrow.')
        return redirect('home')

    escrow.save()

    # Check if both approved
    if escrow.both_approved():
        # Default to landlord release (can be changed)
        escrow.release_to_landlord()
        messages.success(request, 'Both parties have approved! Funds have been released to the landlord.')

    return redirect('escrow_detail', property_id=escrow.property.id)


# core/views.py

@login_required
@landlord_verified_required
def manage_occupancy(request, request_id):
    """Landlord approves/rejects occupancy request"""
    occupancy_request = get_object_or_404(OccupancyRequest, id=request_id, property__landlord=request.user)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'approve':
            # Mark that offline rent was paid
            escrow = Escrow.objects.get(
                tenant=occupancy_request.tenant,
                property=occupancy_request.property,
                escrow_type='occupancy'
            )
            escrow.offline_rent_paid = True
            escrow.save()

            # Update occupancy request
            occupancy_request.status = 'approved'
            occupancy_request.reviewed_at = timezone.now()
            occupancy_request.save()

            # Update property status
            property = occupancy_request.property
            property.occupancy_status = 'occupied'
            property.reservation_status = 'occupied'
            property.save()

            messages.success(request, f'Occupancy approved for {occupancy_request.tenant.username}')

        elif action == 'reject':
            occupancy_request.status = 'rejected'
            occupancy_request.reviewed_at = timezone.now()
            occupancy_request.save()

            # Refund deposit?
            messages.info(request, f'Occupancy rejected for {occupancy_request.tenant.username}')

        return redirect('landlord_dashboard')

    context = {
        'request': occupancy_request,
        'tenant': occupancy_request.tenant,
        'property': occupancy_request.property,
    }
    return render(request, 'manage_occupancy.html', context)


@login_required
def upload_escrow_evidence(request, escrow_id):
    """Upload evidence for escrow release"""
    escrow = get_object_or_404(Escrow, id=escrow_id)

    if request.method == 'POST' and request.FILES.get('evidence'):
        if request.user == escrow.tenant:
            escrow.tenant_evidence = request.FILES['evidence']
            messages.success(request, 'Evidence uploaded successfully.')
        elif request.user == escrow.landlord:
            escrow.landlord_evidence = request.FILES['evidence']
            messages.success(request, 'Evidence uploaded successfully.')
        else:
            messages.error(request, 'You do not have permission to upload evidence.')
            return redirect('home')

        escrow.save()

    return redirect('escrow_detail', property_id=escrow.property.id)


from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from .models import Property, User, ChatMessage


@login_required
def chat_with_landlord(request, property_id):
    """
    Chat interface between tenant and landlord for a specific property
    """
    property = get_object_or_404(Property, id=property_id)

    # Determine the other party based on user type
    if request.user == property.landlord:
        # Landlord is viewing - they need to select a tenant
        # Get all tenants who have interacted with this property
        from .models import Interest, Reservation, Escrow

        tenant_ids = set()

        # Get tenants from interests
        for interest in Interest.objects.filter(property=property):
            tenant_ids.add(interest.tenant.id)

        # Get tenants from reservations
        for reservation in Reservation.objects.filter(property=property):
            tenant_ids.add(reservation.tenant.id)

        # Get tenants from escrows
        for escrow in Escrow.objects.filter(property=property):
            tenant_ids.add(escrow.tenant.id)

        tenants = User.objects.filter(id__in=tenant_ids)

        # Check if a specific tenant is selected
        selected_tenant_id = request.GET.get('tenant')
        other_user = None
        messages = []

        if selected_tenant_id:
            other_user = get_object_or_404(User, id=selected_tenant_id)
            messages = ChatMessage.objects.filter(
                (Q(sender=request.user, recipient=other_user) |
                 Q(sender=other_user, recipient=request.user)),
                property=property
            ).order_by('timestamp')

            # Mark unread messages as read
            messages.filter(recipient=request.user, is_read=False).update(is_read=True)

        context = {
            'property': property,
            'tenants': tenants,
            'selected_tenant': other_user,
            'messages': messages,
            'chat_partner': other_user,
            'is_landlord': True,
        }

    else:
        # Tenant is viewing - chat directly with landlord
        other_user = property.landlord
        messages = ChatMessage.objects.filter(
            (Q(sender=request.user, recipient=other_user) |
             Q(sender=other_user, recipient=request.user)),
            property=property
        ).order_by('timestamp')

        # Mark unread messages as read
        messages.filter(recipient=request.user, is_read=False).update(is_read=True)

        context = {
            'property': property,
            'landlord': other_user,
            'messages': messages,
            'chat_partner': other_user,
            'is_landlord': False,
        }

    return render(request, 'chat.html', context)


import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from .models import ChatMessage, Property, User


@login_required
def send_chat_message(request):
    """
    AJAX endpoint to send a message
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
        property_id = data.get('property_id')
        recipient_id = data.get('recipient_id')
        message_text = data.get('message')

        if not all([property_id, recipient_id, message_text]):
            return JsonResponse({'error': 'Missing fields'}, status=400)

        property = get_object_or_404(Property, id=property_id)
        recipient = get_object_or_404(User, id=recipient_id)

        # Verify user is part of this conversation
        if not (request.user == property.landlord or request.user in [i.tenant for i in property.interests.all()]):
            return JsonResponse({'error': 'Not authorized'}, status=403)

        message = ChatMessage.objects.create(
            sender=request.user,
            recipient=recipient,
            property=property,
            message=message_text
        )

        return JsonResponse({
            'success': True,
            'message_id': message.id,
            'timestamp': message.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'message': message.message,
            'sender': message.sender.username
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def get_chat_messages(request, property_id, other_user_id):
    """
    AJAX endpoint to get new messages
    """
    property = get_object_or_404(Property, id=property_id)
    other_user = get_object_or_404(User, id=other_user_id)

    last_id = request.GET.get('last_id', 0)

    messages = ChatMessage.objects.filter(
        (Q(sender=request.user, recipient=other_user) |
         Q(sender=other_user, recipient=request.user)),
        property=property,
        id__gt=last_id
    ).order_by('timestamp')

    # Mark received messages as read
    messages.filter(recipient=request.user, is_read=False).update(is_read=True)

    messages_data = [{
        'id': m.id,
        'message': m.message,
        'sender': m.sender.username,
        'timestamp': m.timestamp.strftime('%H:%M'),
        'is_me': m.sender == request.user
    } for m in messages]

    return JsonResponse({'messages': messages_data})


@login_required
def get_unread_count(request):
    """Get count of unread messages for current user"""
    count = ChatMessage.objects.filter(
        recipient=request.user,
        is_read=False
    ).count()

    return JsonResponse({'unread_count': count})

@login_required
@landlord_verified_required
def withdraw_funds(request):
    """Placeholder for withdrawal functionality"""
    messages.info(request, 'Withdrawal feature coming soon!')
    return redirect('landlord_dashboard')



def clear_messages(request):
    """Clear all messages from the session"""
    if request.method == 'POST':
        # This iterates through and consumes all messages
        storage = messages.get_messages(request)
        for message in storage:
            # Just iterating marks them as read
            pass
        storage.used = True
        return JsonResponse({'status': 'cleared'})
    return JsonResponse({'status': 'error'}, status=400)



"""//APIS"""


@login_required
def api_escrow_detail(request, escrow_id):
    """API endpoint to get escrow details"""
    try:
        escrow = Escrow.objects.get(id=escrow_id)

        # Check permission
        if request.user not in [escrow.tenant, escrow.landlord]:
            return JsonResponse({'error': 'Permission denied'}, status=403)

        data = {
            'id': escrow.id,
            'status': escrow.status,
            'status_display': escrow.get_status_display(),
            'created_at': escrow.created_at.strftime('%B %d, %Y'),
            'amount': float(escrow.amount),
            'amount_formatted': f"{escrow.amount:,.0f}",
            'type_display': escrow.get_escrow_type_display(),
            'tenant_name': escrow.tenant.get_full_name() or escrow.tenant.username,
            'tenant_email': escrow.tenant.email,
            'tenant_approved': escrow.tenant_approved,
            'landlord_name': escrow.landlord.get_full_name() or escrow.landlord.username,
            'landlord_email': escrow.landlord.email,
            'landlord_approved': escrow.landlord_approved,
            'tenant_evidence': escrow.tenant_evidence.url if escrow.tenant_evidence else None,
            'landlord_evidence': escrow.landlord_evidence.url if escrow.landlord_evidence else None,
            'can_approve_tenant': request.user == escrow.tenant and not escrow.tenant_approved,
            'can_approve_landlord': request.user == escrow.landlord and not escrow.landlord_approved,
        }
        return JsonResponse(data)
    except Escrow.DoesNotExist:
        return JsonResponse({'error': 'Escrow not found'}, status=404)


from django.db.models import Q, Max, Count
from .models import ChatMessage, Property


@login_required
def all_chats(request):
    """Show all conversations for the current user"""
    if request.user.profile.user_type == 'landlord':
        # Landlord sees conversations about their properties
        # Get all properties owned by this landlord
        properties = Property.objects.filter(landlord=request.user)

        # For each property, get the latest message and unread count
        conversations = []
        for property in properties:
            # Get all messages for this property
            messages = ChatMessage.objects.filter(property=property)

            # Get unique conversation partners (tenants)
            partners = User.objects.filter(
                Q(sent_messages__property=property, sent_messages__recipient=request.user) |
                Q(received_messages__property=property, received_messages__sender=request.user)
            ).distinct()

            for partner in partners:
                # Get latest message
                latest = messages.filter(
                    Q(sender=partner, recipient=request.user) |
                    Q(sender=request.user, recipient=partner)
                ).order_by('-timestamp').first()

                # Get unread count
                unread = messages.filter(
                    sender=partner,
                    recipient=request.user,
                    is_read=False
                ).count()

                conversations.append({
                    'property': property,
                    'partner': partner,
                    'latest_message': latest,
                    'unread_count': unread,
                    'last_message_time': latest.timestamp if latest else None,
                })

        # Sort by latest message time
        conversations.sort(key=lambda x: x['last_message_time'] or datetime.min, reverse=True)

    else:
        # Tenant sees conversations with landlords about properties they've interacted with
        # Get all messages where user is involved
        user_messages = ChatMessage.objects.filter(
            Q(sender=request.user) | Q(recipient=request.user)
        ).select_related('property', 'sender', 'recipient')

        # Group by property and partner
        conversation_map = {}
        for msg in user_messages:
            partner = msg.sender if msg.recipient == request.user else msg.recipient
            key = f"{msg.property.id}_{partner.id}"

            if key not in conversation_map:
                conversation_map[key] = {
                    'property': msg.property,
                    'partner': partner,
                    'latest_message': msg,
                    'last_message_time': msg.timestamp,
                    'unread_count': 0
                }
            else:
                if msg.timestamp > conversation_map[key]['last_message_time']:
                    conversation_map[key]['latest_message'] = msg
                    conversation_map[key]['last_message_time'] = msg.timestamp

            # Count unread messages from partner
            if msg.sender == partner and msg.recipient == request.user and not msg.is_read:
                conversation_map[key]['unread_count'] += 1

        conversations = list(conversation_map.values())
        conversations.sort(key=lambda x: x['last_message_time'], reverse=True)

    context = {
        'conversations': conversations,
        'is_landlord': request.user.profile.user_type == 'landlord',
    }
    return render(request, 'all_chats.html', context)