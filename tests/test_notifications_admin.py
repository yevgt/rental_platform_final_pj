import pytest
from types import SimpleNamespace

from django.contrib import admin

import notifications.admin as na


def make_admin_with_fields(monkeypatch, present_fields):
    # Stub has_field to simulate model fields presence
    def _has_field(model, name: str) -> bool:
        return name in present_fields

    monkeypatch.setattr(na, "has_field", _has_field, raising=True)

    # Create a NotificationAdmin instance without calling __init__
    admin_inst = na.NotificationAdmin.__new__(na.NotificationAdmin)
    # Simulate "model" attribute; content is irrelevant because we stub has_field
    admin_inst.model = object()
    return admin_inst


def test_get_list_display_constant():
    admin_inst = na.NotificationAdmin.__new__(na.NotificationAdmin)
    assert admin_inst.get_list_display(request=None) == (
        "id",
        "recipient_col",
        "type_col",
        "is_read_col",
        "related_col",
        "created_col",
    )


def test_get_search_fields_all_variants(monkeypatch):
    present = {
        # text/title fields
        "title", "message", "text", "body",
        # user relations
        "user", "recipient", "to_user", "sender",
    }
    admin_inst = make_admin_with_fields(monkeypatch, present)
    fields = admin_inst.get_search_fields(request=None)
    # Should include all recognized fields mapped to email for relations
    assert set(fields) == {
        "title", "message", "text", "body",
        "user__email", "recipient__email", "to_user__email", "sender__email",
    }


def test_get_list_filter_includes_bool_type_and_date(monkeypatch):
    present = {
        # boolean read flags (both exist, but only first is taken)
        "is_read", "read",
        # type-like fields
        "type", "category", "kind", "channel",
        # date-like fields (first existing is used)
        "created_at", "created", "timestamp", "sent_at",
    }
    admin_inst = make_admin_with_fields(monkeypatch, present)
    filters = admin_inst.get_list_filter(request=None)

    # First boolean found: is_read
    assert filters[0] == "is_read"
    # All type/category/kind/channel are included
    assert "type" in filters and "category" in filters and "kind" in filters and "channel" in filters
    # Date filter tuple present and uses the first available = created_at
    assert ("created_at", admin.DateFieldListFilter) in filters


def test_get_ordering_prefers_created_at(monkeypatch):
    present = {"created_at"}
    admin_inst = make_admin_with_fields(monkeypatch, present)
    assert admin_inst.get_ordering(request=None) == ("-created_at",)


def test_get_ordering_fallback_to_id(monkeypatch):
    present = set()  # no date-like fields at all
    admin_inst = make_admin_with_fields(monkeypatch, present)
    assert admin_inst.get_ordering(request=None) == ("-id",)


def test_get_list_select_related(monkeypatch):
    present = {"user", "property", "booking"}  # 'recipient' and 'sender' absent
    admin_inst = make_admin_with_fields(monkeypatch, present)
    rels = admin_inst.get_list_select_related(request=None)
    assert rels == ("user", "property", "booking")


def test_recipient_col_prefers_user_email():
    user = SimpleNamespace(email="user@example.com")
    obj = SimpleNamespace(user=user)
    admin_inst = na.NotificationAdmin.__new__(na.NotificationAdmin)
    assert admin_inst.recipient_col(obj) == "user@example.com"


def test_recipient_col_fallback_to_recipient_str_when_no_email():
    obj = SimpleNamespace(recipient="john.doe")  # string has no 'email'
    admin_inst = na.NotificationAdmin.__new__(na.NotificationAdmin)
    assert admin_inst.recipient_col(obj) == "john.doe"


def test_recipient_col_none_when_no_known_fields():
    obj = SimpleNamespace()
    admin_inst = na.NotificationAdmin.__new__(na.NotificationAdmin)
    assert admin_inst.recipient_col(obj) is None


def test_type_col_checks_order():
    obj1 = SimpleNamespace(type="TYPE_A", category="CAT_B")
    obj2 = SimpleNamespace(category="CAT_ONLY")
    obj3 = SimpleNamespace(kind="KIND_ONLY")
    obj4 = SimpleNamespace(channel="EMAIL")

    admin_inst = na.NotificationAdmin.__new__(na.NotificationAdmin)

    assert admin_inst.type_col(obj1) == "TYPE_A"      # 'type' wins
    assert admin_inst.type_col(obj2) == "CAT_ONLY"    # next: 'category'
    assert admin_inst.type_col(obj3) == "KIND_ONLY"   # then: 'kind'
    assert admin_inst.type_col(obj4) == "EMAIL"       # lastly: 'channel'
    assert admin_inst.type_col(SimpleNamespace()) is None


def test_is_read_col_variants():
    admin_inst = na.NotificationAdmin.__new__(na.NotificationAdmin)

    # is_read present -> used as source of truth
    assert admin_inst.is_read_col(SimpleNamespace(is_read=True)) is True
    assert admin_inst.is_read_col(SimpleNamespace(is_read=False, read=True)) is False

    # Without is_read -> fallback to read
    assert admin_inst.is_read_col(SimpleNamespace(read=True)) is True

    # read_at present -> treated as read
    assert admin_inst.is_read_col(SimpleNamespace(read_at="2025-01-01T00:00:00")) is True

    # No hints at all -> False
    assert admin_inst.is_read_col(SimpleNamespace()) is False


def test_related_col_variants():
    booking = SimpleNamespace(id=1)
    prop = SimpleNamespace(id=2)
    something = SimpleNamespace(name="obj")
    obj1 = SimpleNamespace(booking=booking)
    obj2 = SimpleNamespace(property=prop)
    obj3 = SimpleNamespace(object=something)
    obj4 = SimpleNamespace(content_object="content")

    admin_inst = na.NotificationAdmin.__new__(na.NotificationAdmin)

    assert admin_inst.related_col(obj1) is booking
    assert admin_inst.related_col(obj2) is prop
    assert admin_inst.related_col(obj3) is something
    assert admin_inst.related_col(obj4) == "content"
    assert admin_inst.related_col(SimpleNamespace()) is None


def test_created_col_variants():
    admin_inst = na.NotificationAdmin.__new__(na.NotificationAdmin)
    assert admin_inst.created_col(SimpleNamespace(created_at=1)) == 1
    assert admin_inst.created_col(SimpleNamespace(created=2)) == 2
    assert admin_inst.created_col(SimpleNamespace(timestamp=3)) == 3
    assert admin_inst.created_col(SimpleNamespace(sent_at=4)) == 4
    assert admin_inst.created_col(SimpleNamespace()) is None