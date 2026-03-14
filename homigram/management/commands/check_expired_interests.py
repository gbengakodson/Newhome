# core/management/commands/check_expired_interests.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from homigram.models import Interest
from datetime import timedelta


class Command(BaseCommand):
    help = 'Check for expired interests and flag landlords who didnt respond'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without actually updating the database',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        # Find pending interests that have expired
        now = timezone.now()
        expired = Interest.objects.filter(
            status='pending',
            expires_at__lt=now
        )

        count = expired.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS('No expired interests found.'))
            return

        self.stdout.write(f"Found {count} expired interest(s)")

        for interest in expired:
            self.stdout.write(f"\nProcessing Interest #{interest.id}:")
            self.stdout.write(f"  Tenant: {interest.tenant.username}")
            self.stdout.write(f"  Property: {interest.property.title}")
            self.stdout.write(f"  Landlord: {interest.property.landlord.username}")
            self.stdout.write(f"  Expired: {interest.expires_at}")

            if dry_run:
                self.stdout.write(self.style.WARNING("  [DRY RUN] Would expire and flag"))
            else:
                # Expire the interest
                interest.status = 'expired'
                interest.save()

                # Flag the landlord
                landlord = interest.property.landlord
                landlord.profile.flag_count += 1
                landlord.profile.save()

                self.stdout.write(
                    self.style.SUCCESS(f"  ✓ Landlord flagged (total flags: {landlord.profile.flag_count})"))

                # Check if account should be disabled
                if landlord.profile.flag_count >= 7:
                    landlord.profile.account_disabled = True
                    landlord.profile.disabled_at = timezone.now()
                    landlord.profile.save()
                    self.stdout.write(self.style.ERROR(f"  ⚠ Account DISABLED - reached 7 flags"))

        if dry_run:
            self.stdout.write(self.style.WARNING(f"\nDRY RUN completed. {count} interests would be processed."))
        else:
            self.stdout.write(self.style.SUCCESS(f"\nSuccessfully processed {count} expired interests."))