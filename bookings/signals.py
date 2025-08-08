from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import Booking
from notifications.models import Notification

@receiver(pre_save, sender=Booking)
def booking_store_old_status(sender, instance: Booking, **kwargs):
    if instance.pk:
        try:
            old = Booking.objects.get(pk=instance.pk)
            instance._old_status = old.status
        except Booking.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None

@receiver(post_save, sender=Booking)
def booking_notifications(sender, instance: Booking, created, **kwargs):
    if created:
        # Новый запрос на букинг -> уведомление арендодателю
        landlord = instance.property.owner
        Notification.objects.create(
            user=landlord,
            type=Notification.Types.BOOKING_NEW,
            message=f"Новая заявка на бронирование по объекту '{instance.property.title}' от {instance.user.email}.",
        )
    else:
        # Изменение статуса -> уведомление арендатору при подтверждении/отклонении
        old_status = getattr(instance, "_old_status", None)
        if old_status and old_status != instance.status:
            if instance.status == Booking.Status.CONFIRMED:
                Notification.objects.create(
                    user=instance.user,
                    type=Notification.Types.BOOKING_CONFIRMED,
                    message=f"Ваша бронь по '{instance.property.title}' подтверждена.",
                )
            elif instance.status == Booking.Status.REJECTED:
                Notification.objects.create(
                    user=instance.user,
                    type=Notification.Types.BOOKING_REJECTED,
                    message=f"Ваша бронь по '{instance.property.title}' отклонена.",
                )