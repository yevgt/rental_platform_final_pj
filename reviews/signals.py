from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Review

# Notification may differ in implementation, so import in try/except
try:
    from notifications.models import Notification  # check the app name, if it's different, correct it
except Exception:
    Notification = None


def _resolve_notification_type():
    """
    Trying to find the correct value for the Notification.type field among the different options:
    - Notification.Type.REVIEW_NEW (or NEW_REVIEW/REVIEW_CREATED/REVIEW)
    - Notification.Types.REVIEW_NEW (alternate name)
    - Notification.TypeChoices.REVIEW_NEW
    - First element from choices
    - String fallback "review_new" if the 'type' field exists
    """
    if Notification is None:
        return None

    for attr_name in ("Type", "Types", "TypeChoices"):
        if hasattr(Notification, attr_name):
            ChoiceCls = getattr(Notification, attr_name)
            for candidate in ("REVIEW_NEW", "NEW_REVIEW", "REVIEW_CREATED", "REVIEW"):
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
            return "review_new"
    except Exception:
        pass

    return None


@receiver(post_save, sender=Review)
def notify_owner_on_new_review(sender, instance: Review, created, **kwargs):
    """
    Creates a notification to the object owner when a new review is created.
    Any errors in creating the notification should NOT break the review saving.
    """
    if not created or Notification is None:
        return

    property_obj = getattr(instance, "property", None)
    if property_obj is None:
        return

    owner = getattr(property_obj, "owner", None)
    if owner is None:
        return

    # We do not notify if the owner = author
    owner_id = getattr(owner, "id", None)
    if owner_id == getattr(instance, "user_id", None):
        return

    notif_type = _resolve_notification_type()
    payload = {
        "property_id": getattr(property_obj, "id", None),
        "property_title": getattr(property_obj, "title", None),
        "review_id": getattr(instance, "id", None),
        "rating": getattr(instance, "rating", None),
    }

    create_kwargs = {"user": owner, "data": payload}
    if notif_type is not None:
        create_kwargs["type"] = notif_type

    try:
        Notification.objects.create(**create_kwargs)
    except Exception:
        # best-effort notifications — don't crash
        pass
