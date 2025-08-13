from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

from .models import Booking

try:
    from notifications.models import Notification
except Exception:
    Notification = None


def _resolve_notif_value(*candidates: str):
    """
    Вернуть значение для Notification.type из возможных контейнеров (Type/Types/TypeChoices),
    либо строковый fallback, если в модели есть поле 'type'.
    """
    if Notification is None:
        return None

    for attr_name in ("Type", "Types", "TypeChoices"):
        if hasattr(Notification, attr_name):
            ChoiceCls = getattr(Notification, attr_name)
            for candidate in candidates:
                if hasattr(ChoiceCls, candidate):
                    return getattr(ChoiceCls, candidate)
            if hasattr(ChoiceCls, "choices") and getattr(ChoiceCls, "choices"):
                try:
                    return ChoiceCls.choices[0][0]
                except Exception:
                    pass

    try:
        field_names = {f.name for f in Notification._meta.fields}
        if "type" in field_names:
            # Возьмем первый из кандидатов в нижнем регистре как fallback
            return candidates[0].lower()
    except Exception:
        pass

    return None


@receiver(pre_save, sender=Booking)
def store_previous_status(sender, instance: Booking, **kwargs):
    if instance.pk:
        try:
            prev = Booking.objects.get(pk=instance.pk)
            instance._previous_status = prev.status
        except Booking.DoesNotExist:
            instance._previous_status = None
    else:
        instance._previous_status = None


@receiver(post_save, sender=Booking)
def notify_on_booking_events(sender, instance: Booking, created, **kwargs):
    if Notification is None:
        return

    prop = getattr(instance, "property", None)
    landlord = getattr(prop, "owner", None)
    renter = getattr(instance, "user", None)

    # 1) Новая заявка -> уведомление арендодателю
    if created and getattr(instance, "status", None) == getattr(Booking.Status, "PENDING", "pending") and landlord:
        notif_type = _resolve_notif_value("BOOKING_NEW", "NEW_BOOKING")
        payload = {
            "booking_id": getattr(instance, "id", None),
            "property_id": getattr(prop, "id", None),
            "property_title": getattr(prop, "title", None),
            "renter_id": getattr(renter, "id", None),
        }
        kwargs = {"user": landlord, "data": payload}
        if notif_type is not None:
            kwargs["type"] = notif_type
        try:
            Notification.objects.create(**kwargs)
        except Exception:
            pass

    # 2) Смена статуса -> уведомление арендатору
    prev_status = getattr(instance, "_previous_status", None)
    new_status = getattr(instance, "status", None)
    if not created and renter and prev_status != new_status:
        # CONFIRMED
        if new_status == getattr(Booking.Status, "CONFIRMED", "confirmed"):
            notif_type = _resolve_notif_value("BOOKING_CONFIRMED", "CONFIRMED")
        # REJECTED
        elif new_status == getattr(Booking.Status, "REJECTED", "rejected"):
            notif_type = _resolve_notif_value("BOOKING_REJECTED", "REJECTED")
        else:
            notif_type = None

        if notif_type is not None:
            payload = {
                "booking_id": getattr(instance, "id", None),
                "property_id": getattr(prop, "id", None),
                "property_title": getattr(prop, "title", None),
                "status": new_status,
            }
            data = {"user": renter, "data": payload, "type": notif_type}
            try:
                Notification.objects.create(**data)
            except Exception:
                pass
