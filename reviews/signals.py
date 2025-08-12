from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Review

# Notification может отличаться по реализации, поэтому импорт в try/except
try:
    from notifications.models import Notification  # проверь имя app'а, если другое — поправь
except Exception:
    Notification = None


def _resolve_notification_type():
    """
    Пытаемся найти корректное значение для поля Notification.type среди разных вариантов:
    - Notification.Type.REVIEW_NEW (или NEW_REVIEW/REVIEW_CREATED/REVIEW)
    - Notification.Types.REVIEW_NEW (альтернативное имя)
    - Notification.TypeChoices.REVIEW_NEW
    - Первый элемент из choices
    - Строковый fallback "review_new", если поле 'type' существует
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
    Создаёт уведомление владельцу объекта при создании нового отзыва.
    Любые ошибки при создании уведомления НЕ должны ломать сохранение отзыва.
    """
    if not created or Notification is None:
        return

    property_obj = getattr(instance, "property", None)
    if property_obj is None:
        return

    owner = getattr(property_obj, "owner", None)
    if owner is None:
        return

    # Не уведомляем, если владелец = автор
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
        # уведомления best-effort — не падаем
        pass

# from django.db.models.signals import post_save
# from django.dispatch import receiver
# from .models import Review
# from notifications.models import Notification
#
# @receiver(post_save, sender=Review)
# def notify_owner_on_new_review(sender, instance: Review, created, **kwargs):
#     if not created:
#         return
#     property_obj = instance.property
#     owner = property_obj.owner
#     # Не уведомляем, если владелец сам пишет отзыв (теоретически невозможно, но на всякий случай)
#     if owner_id := getattr(owner, "id", None):
#         if owner_id == instance.user_id:
#             return
#     Notification.objects.create(
#         user=owner,
#         type=Notification.Type.REVIEW_NEW,  # убедись что такой тип есть
#         data={
#             "property_id": property_obj.id,
#             "property_title": property_obj.title,
#             "review_id": instance.id,
#             "rating": instance.rating,
#         },
#     )