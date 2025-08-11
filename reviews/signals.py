from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Review
from notifications.models import Notification

@receiver(post_save, sender=Review)
def notify_owner_on_new_review(sender, instance: Review, created, **kwargs):
    if not created:
        return
    property_obj = instance.property
    owner = property_obj.owner
    # Не уведомляем, если владелец сам пишет отзыв (теоретически невозможно, но на всякий случай)
    if owner_id := getattr(owner, "id", None):
        if owner_id == instance.user_id:
            return
    Notification.objects.create(
        user=owner,
        type=Notification.Type.REVIEW_NEW,  # убедись что такой тип есть
        data={
            "property_id": property_obj.id,
            "property_title": property_obj.title,
            "review_id": instance.id,
            "rating": instance.rating,
        },
    )