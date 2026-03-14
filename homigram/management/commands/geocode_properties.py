# core/management/commands/geocode_properties.py
from django.core.management.base import BaseCommand
from homigram.models import Property
from homigram.utils.geocoding import geocode_property  # Note: geocode_property (singular)


class Command(BaseCommand):
    help = 'Geocode all properties without coordinates'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without saving to database',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        # Find properties missing coordinates
        properties = Property.objects.filter(
            latitude__isnull=True
        ) | Property.objects.filter(
            longitude__isnull=True
        )

        total = properties.count()
        self.stdout.write(f"Found {total} properties without coordinates")

        success = 0
        failed = 0

        for prop in properties:
            self.stdout.write(f"Geocoding: {prop.title} - {prop.full_address}")

            if dry_run:
                self.stdout.write(self.style.WARNING(f"  [DRY RUN] Would geocode this property"))
                success += 1
            else:
                if geocode_property(prop):  # Calling the singular function
                    self.stdout.write(self.style.SUCCESS(f"  ✅ Success: {prop.latitude}, {prop.longitude}"))
                    success += 1
                else:
                    self.stdout.write(self.style.ERROR(f"  ❌ Failed"))
                    failed += 1

        self.stdout.write(self.style.SUCCESS(f"\nCompleted: {success} succeeded, {failed} failed"))