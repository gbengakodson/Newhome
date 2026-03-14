# homigram/forms.py
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import Property, PropertyImage, PropertyFeature, Profile, Escrow



class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={
        'class': 'form-control',
        'placeholder': 'Enter your email'
    }))
    username = forms.CharField(widget=forms.TextInput(attrs={
        'class': 'form-control',
        'placeholder': 'Choose a username'
    }))
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput(attrs={
        'class': 'form-control',
        'placeholder': 'Create a password'
    }))
    password2 = forms.CharField(label='Confirm Password', widget=forms.PasswordInput(attrs={
        'class': 'form-control',
        'placeholder': 'Confirm your password'
    }))
    user_type = forms.ChoiceField(choices=Profile.USER_TYPES, widget=forms.Select(attrs={
        'class': 'form-control'
    }))
    phone = forms.CharField(max_length=15, required=False, widget=forms.TextInput(attrs={
        'class': 'form-control',
        'placeholder': 'Enter your phone number (optional)'
    }))

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2', 'user_type', 'phone']

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('This email is already registered.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.is_active = False  # User is inactive until email verification

        if commit:
            user.save()
            # Update profile with additional data
            profile = user.profile
            profile.user_type = self.cleaned_data['user_type']
            profile.phone = self.cleaned_data['phone']
            profile.save()

        return user


# core/forms.py
from django import forms
from .models import Profile


class VerificationSubmissionForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['id_type', 'id_number', 'id_document', 'passport_photo']
        widgets = {
            'id_type': forms.Select(attrs={'class': 'form-control'}),
            'id_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter ID number'}),
            'id_document': forms.FileInput(attrs={'class': 'form-control', 'accept': '.pdf,.jpg,.jpeg,.png'}),
            'passport_photo': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        }

    def clean_id_document(self):
        file = self.cleaned_data.get('id_document')
        if file:
            if file.size > 5 * 1024 * 1024:
                raise forms.ValidationError("File size must be less than 5MB")
            ext = file.name.split('.')[-1].lower()
            if ext not in ['pdf', 'jpg', 'jpeg', 'png']:
                raise forms.ValidationError("Only PDF, JPG, JPEG, and PNG files are allowed")
        return file

    def clean_passport_photo(self):
        file = self.cleaned_data.get('passport_photo')
        if file:
            if file.size > 2 * 1024 * 1024:
                raise forms.ValidationError("Photo size must be less than 2MB")
            ext = file.name.split('.')[-1].lower()
            if ext not in ['jpg', 'jpeg', 'png']:
                raise forms.ValidationError("Only JPG, JPEG, and PNG files are allowed")
        return file

#forms.py - Simplified version without images field


class PropertyForm(forms.ModelForm):
    features = forms.ModelMultipleChoiceField(
        queryset=PropertyFeature.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    class Meta:
        model = Property
        fields = [
            'title', 'description', 'address', 'city', 'state', 'zipcode',
            'price', 'bedrooms', 'bathrooms', 'sqft', 'features', 'rental_agreement'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'address': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'state': forms.TextInput(attrs={'class': 'form-control'}),
            'zipcode': forms.TextInput(attrs={'class': 'form-control'}),
            'price': forms.NumberInput(attrs={'class': 'form-control'}),
            'bedrooms': forms.NumberInput(attrs={'class': 'form-control'}),
            'bathrooms': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
            'sqft': forms.NumberInput(attrs={'class': 'form-control'}),
            'rental_agreement': forms.FileInput(attrs={'class': 'form-control'}),
        }