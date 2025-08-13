import sys
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from bookings.models import Booking

class Command(BaseCommand):
    help = "Marks reservations with status CONFIRMED and past end_date as COMPLETED."

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            help="Bulk size of the update (default 500)).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what will be done without actually updating.",
        )
        parser.add_argument(
            "--days-back",
            type=int,
            default=90,
            help="Limit processing to bookings whose end_date is not older than N days (optimization). "
                 "0 = without limitation.",
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        dry_run = options["dry_run"]
        days_back = options["days_back"]

        today = timezone.now().date()
        qs = Booking.objects.filter(
            status=Booking.Status.CONFIRMED,
            end_date__lt=today,
        )

        if days_back > 0:
            cutoff = today - timezone.timedelta(days=days_back)
            qs = qs.filter(end_date__gte=cutoff)

        total = qs.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS("No bookings to complete."))
            return

        self.stdout.write(f"Found {total} confirmed completed bookings.")

        if dry_run:
            sample = list(qs.order_by("end_date").values_list("id", "end_date")[:10])
            self.stdout.write(f"[DRY RUN] Example of the first 10: {sample}")
            self.stdout.write(self.style.WARNING("Dry run: no updates performed."))
            return

        updated = 0
        while True:
            ids = list(qs.values_list("id", flat=True)[:batch_size])
            if not ids:
                break
            with transaction.atomic():
                batch_qs = Booking.objects.select_for_update().filter(id__in=ids)
                for booking in batch_qs:
                    if booking.end_date < today and booking.status == Booking.Status.CONFIRMED:
                        booking.status = Booking.Status.COMPLETED
                        booking.completed_at = timezone.now()
                        booking.save(update_fields=["status", "completed_at"])
                        updated += 1
            self.stdout.write(f"Processed {updated}/{total} ...")

        self.stdout.write(self.style.SUCCESS(f"Done. Completed {updated} bookings."))