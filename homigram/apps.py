from django.apps import AppConfig
from django.apps import AppConfig
from django.contrib.auth import get_user_model



class HomigramConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'homigram'


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        # Create system user if not exists
        User = get_user_model()
        if not User.objects.filter(username='system').exists():
            User.objects.create_user(username='system', email='system@localhost', password='<random>', is_active=True)
            # You might want to set a random password or make it unusable


# In a data migration or in apps.py ready() method
def create_default_features():
    features = [
        {'name': 'WiFi', 'icon': 'fa-wifi'},
        {'name': 'Compound Generator', 'icon': 'fa-bolt'},
        {'name': 'Steady Light', 'icon': 'fa-lightbulb'},
        {'name': 'Water System', 'icon': 'fa-water'},
        {'name': 'Furnished', 'icon': 'fa-couch'},
        {'name': 'Waste Disposal', 'icon': 'fa-trash'},
        {'name': 'Security System', 'icon': 'fa-shield-alt'},
    ]
    for feature in features:
        PropertyFeature.objects.get_or_create(name=feature['name'], defaults={'icon': feature['icon']})