from django.contrib import admin
from django.apps import apps

# Trying to get the Notification model from the notifications app (or notification)
Notification = None
for app_label in ("notifications", "notification"):
    try:
        Notification = apps.get_model(app_label, "Notification")
        if Notification:
            break
    except LookupError:
        continue


def has_field(model, name: str) -> bool:
    return any(f.name == name for f in model._meta.get_fields())


class NotificationAdmin(admin.ModelAdmin):
    """
    Dynamic notification admin panel:
    - list_display: id, recipient, type, read?, related object, created
    - search: by text/title and recipient/sender email
    - filters: read, type/category, channel, date
    - sort: by -created_at/-created/-timestamp/-id
    """

    def get_list_display(self, request):
        return ("id", "recipient_col", "type_col", "is_read_col", "related_col", "created_col")

    def get_search_fields(self, request):
        fields = []
        # Text/heading
        for name in ("title", "message", "text", "body"):
            if has_field(self.model, name):
                fields.append(name)
        # Email recipient/sender
        if has_field(self.model, "user"):
            fields.append("user__email")
        if has_field(self.model, "recipient"):
            fields.append("recipient__email")
        if has_field(self.model, "to_user"):
            fields.append("to_user__email")
        if has_field(self.model, "sender"):
            fields.append("sender__email")
        return tuple(fields)

    def get_list_filter(self, request):
        filters = []
        for bool_name in ("is_read", "read"):
            if has_field(self.model, bool_name):
                filters.append(bool_name)
                break
        for choice_name in ("type", "category", "kind", "channel"):
            if has_field(self.model, choice_name):
                filters.append(choice_name)
        # Дата
        date_field = next((n for n in ("created_at", "created", "timestamp", "sent_at") if has_field(self.model, n)), None)
        if date_field:
            filters.append((date_field, admin.DateFieldListFilter))
        return tuple(filters)

    def get_ordering(self, request):
        for name in ("-created_at", "-created", "-timestamp", "-id"):
            base = name.lstrip("-")
            if name.startswith("-") and has_field(self.model, base):
                return (name,)
            if name == "-id":  # id есть всегда
                return (name,)
        return ("-id",)

    def get_list_select_related(self, request):
        rels = []
        for rel in ("user", "recipient", "sender", "property", "booking"):
            if has_field(self.model, rel):
                rels.append(rel)
        return tuple(rels)

    # Callback columns (not tied to specific field names)
    @admin.display(description="Recipient")
    def recipient_col(self, obj):
        for name in ("user", "recipient", "to_user"):
            if hasattr(obj, name):
                val = getattr(obj, name)
                return getattr(val, "email", None) or str(val)
        return None

    @admin.display(description="Type")
    def type_col(self, obj):
        for name in ("type", "category", "kind", "channel"):
            if hasattr(obj, name):
                return getattr(obj, name)
        return None

    @admin.display(boolean=True, description="Read")
    def is_read_col(self, obj):
        for name in ("is_read", "read"):
            if hasattr(obj, name):
                return bool(getattr(obj, name))
        # If there is read_at
        if hasattr(obj, "read_at"):
            return getattr(obj, "read_at") is not None
        return False

    @admin.display(description="Related to")
    def related_col(self, obj):
        for name in ("booking", "property", "object", "content_object"):
            if hasattr(obj, name):
                return getattr(obj, name)
        return None

    @admin.display(description="Created by")
    def created_col(self, obj):
        for name in ("created_at", "created", "timestamp", "sent_at"):
            if hasattr(obj, name):
                return getattr(obj, name)
        return None


if Notification is not None:
    admin.site.register(Notification, NotificationAdmin)