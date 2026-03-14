# homigram/urls.py
from django.contrib.auth import views as auth_views
from . import views
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static




urlpatterns = [

    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='home'), name='logout'),
    path('register/', views.register, name='register'),
    path('verify/<str:uidb64>/<str:token>/', views.verify_email, name='verify_email'),

    # Dashboards
    path('dashboard/tenant/', views.tenant_dashboard, name='tenant_dashboard'),
    path('dashboard/landlord/', views.landlord_dashboard, name='landlord_dashboard'),
    path('profile/landlord/<int:landlord_id>/', views.landlord_profile, name='landlord_profile'),
    path('profile/tenant/<int:tenant_id>/', views.tenant_profile, name='tenant_profile'),

    # Properties
    path('property/add/', views.add_property, name='add_property'),
    path('property/<int:property_id>/edit/', views.edit_property, name='edit_property'),
    path('property/<int:property_id>/', views.secure_property_detail, name='property_detail'),
    path('properties/', views.property_list, name='property_list'),

    # Inspection Payment
    path('property/<int:property_id>/pay-to-inspect/', views.pay_inspection_before_view, name='pay_inspection_before_view'),

    # Verification
    path('verification/submit/', views.submit_verification, name='submit_verification'),

    # Wallet Funding - ADD THESE LINES
    path('wallet/fund/', views.fund_wallet, name='fund_wallet'),
    path('payment/callback/', views.payment_callback, name='payment_callback'),

# Escrow System
    path('property/<int:property_id>/pay-deposit/', views.pay_deposit, name='pay_deposit'),
    path('property/<int:property_id>/escrow/', views.escrow_detail, name='escrow_detail'),
    path('escrow/<int:escrow_id>/approve/', views.approve_escrow_release, name='approve_escrow_release'),
    path('escrow/<int:escrow_id>/upload-evidence/', views.upload_escrow_evidence, name='upload_escrow_evidence'),

    # Chat URLs
    path('chat/property/<int:property_id>/', views.chat_with_landlord, name='chat_with_landlord'),
    path('chat/send/', views.send_chat_message, name='send_chat_message'),
    path('chat/messages/<int:property_id>/<int:other_user_id>/', views.get_chat_messages, name='get_chat_messages'),
    path('chat/unread/', views.get_unread_count, name='get_unread_count'),
    path('chats/', views.all_chats, name='all_chats'),

    path('property/<int:property_id>/pay-to-inspect/', views.pay_inspection_before_view,
         name='pay_inspection_before_view'),

    # Property details (AFTER payment)
    path('property/<int:property_id>/', views.property_detail, name='property_detail'),

    # Rental Agreement URLs
    path('property/<int:property_id>/agreement/', views.view_agreement, name='view_agreement'),
    path('property/<int:property_id>/agreement/sign/', views.sign_agreement, name='sign_agreement'),

    path('property/<int:property_id>/interest/', views.express_interest, name='express_interest'),
    path('interest/<int:interest_id>/manage/', views.manage_interest, name='manage_interest'),
    path('interest/<int:interest_id>/cancel/', views.cancel_interest, name='cancel_interest'),

    path('wallet/withdraw/', views.withdraw_funds, name='withdraw_funds'),

    # Occupancy URLs
    path('property/<int:property_id>/request-occupancy/', views.request_occupancy, name='request_occupancy'),
    path('occupancy/<int:request_id>/manage/', views.manage_occupancy, name='manage_occupancy'),

    # Reservation URLs
    path('property/<int:property_id>/request-reservation/', views.request_reservation, name='request_reservation'),
    path('reservation/<int:reservation_id>/', views.reservation_detail, name='reservation_detail'),
    path('reservation/<int:reservation_id>/manage/', views.manage_reservation, name='manage_reservation'),
    path('reservation/<int:reservation_id>/cancel/', views.cancel_reservation, name='cancel_reservation'),

    path('clear-messages/', views.clear_messages, name='clear_messages'),

    # ... API URLs ...
    path('api/escrow/<int:escrow_id>/', views.api_escrow_detail, name='api_escrow_detail'),

    # Home
    path('', views.home, name='home'),
]


# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)