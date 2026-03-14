# core/utils/geocoding.py
import requests
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def geocode_address(address):
    """Convert address to latitude/longitude"""
    api_key = settings.GOOGLE_MAPS_API_KEY
    base_url = "https://maps.googleapis.com/maps/api/geocode/json"

    params = {
        'address': address,
        'key': api_key
    }

    try:
        response = requests.get(base_url, params=params)
        data = response.json()

        if data['status'] == 'OK':
            location = data['results'][0]['geometry']['location']
            return {
                'lat': location['lat'],
                'lng': location['lng'],
                'formatted_address': data['results'][0]['formatted_address']
            }
        else:
            logger.error(f"Geocoding error: {data['status']}")
            return None

    except Exception as e:
        logger.error(f"Geocoding exception: {e}")
        return None


# ✅ This is the function you're trying to import
def geocode_property(property):  # Note: singular "property"
    """Geocode a property and save coordinates"""
    if property.latitude and property.longitude:
        return True

    full_address = f"{property.address}, {property.city}, {property.state} {property.zipcode}"
    result = geocode_address(full_address)

    if result:
        property.latitude = result['lat']
        property.longitude = result['lng']
        property.save()
        return True

    return False