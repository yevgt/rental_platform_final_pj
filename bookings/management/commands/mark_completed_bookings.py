import sys
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from bookings.models import Booking

class Command(BaseCommand):
    help = "Отмечает бронирования со статусом CONFIRMED и прошедшей end_date как COMPLETED."

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            help="Размер пакета (bulk) для обновления (по умолчанию 500).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Показать, что будет сделано, без реального обновления.",
        )
        parser.add_argument(
            "--days-back",
            type=int,
            default=90,
            help="Ограничить обработку бронированиями, end_date не старше N дней (оптимизация). 0 = без ограничения.",
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
            self.stdout.write(self.style.SUCCESS("Нет бронирований для завершения."))
            return

        self.stdout.write(f"Найдено {total} подтвержденных завершившихся бронирований.")

        if dry_run:
            sample = list(qs.order_by("end_date").values_list("id", "end_date")[:10])
            self.stdout.write(f"[DRY RUN] Пример первых 10: {sample}")
            self.stdout.write(self.style.WARNING("Dry run: обновлений не выполнено."))
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
            self.stdout.write(f"Обработано {updated}/{total} ...")

        self.stdout.write(self.style.SUCCESS(f"Готово. Завершено {updated} бронирований."))