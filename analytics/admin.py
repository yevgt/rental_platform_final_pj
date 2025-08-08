from django.contrib import admin
from django.apps import apps


def has_field(model, name: str) -> bool:
    return any(f.name == name for f in model._meta.get_fields())


class AnalyticsModelAdmin(admin.ModelAdmin):
    """
    Универсальная админка для моделей аналитики.
    Автоматически подбирает:
    - list_display: id, ключевое поле (query/title/property), метрики (views/count), дата
    - search_fields: query/title/property__title/user__email
    - list_filter: по дате, типам/флагам если есть
    - ordering: по убыванию основной метрики или по дате
    """

    def get_primary_text_field(self):
        for n in ("query", "term", "title", "name", "keyword"):
            if has_field(self.model, n):
                return n
        return None

    def get_metric_field(self):
        for n in ("count", "search_count", "views", "views_count", "total", "score"):
            if has_field(self.model, n):
                return n
        return None

    def get_date_field(self):
        for n in ("date", "day", "period", "created_at", "created", "last_used_at", "last_viewed_at"):
            if has_field(self.model, n):
                return n
        return None

    def get_property_field(self):
        for n in ("property", "listing", "estate"):
            if has_field(self.model, n):
                return n
        return None

    def get_user_field(self):
        for n in ("user", "owner", "creator"):
            if has_field(self.model, n):
                return n
        return None

    def get_list_display(self, request):
        items = ["id"]
        p = self.get_primary_text_field()
        prop = self.get_property_field()
        metric = self.get_metric_field()
        date = self.get_date_field()

        if prop:
            items.append("property_col")
        if p:
            items.append("primary_col")
        if metric:
            items.append("metric_col")
        if date:
            items.append("date_col")
        return tuple(items)

    def get_search_fields(self, request):
        fields = []
        p = self.get_primary_text_field()
        prop = self.get_property_field()
        user = self.get_user_field()

        if p:
            fields.append(p)
        if prop:
            fields.extend((f"{prop}__title", f"{prop}__location"))
        if user:
            fields.append(f"{user}__email")
        return tuple(fields)

    def get_list_filter(self, request):
        filters = []
        date = self.get_date_field()
        if date:
            filters.append((date, admin.DateFieldListFilter))
        # Флаги, если есть
        for name in ("is_active", "is_archived", "status", "type"):
            if has_field(self.model, name):
                filters.append(name)
        prop = self.get_property_field()
        user = self.get_user_field()
        if prop:
            filters.append((prop, admin.RelatedOnlyFieldListFilter))
        if user:
            filters.append((user, admin.RelatedOnlyFieldListFilter))
        return tuple(filters)

    def get_ordering(self, request):
        metric = self.get_metric_field()
        if metric:
            return (f"-{metric}",)
        date = self.get_date_field()
        if date:
            return (f"-{date}",)
        return ("-id",)

    def get_list_select_related(self, request):
        rels = []
        for rel in (self.get_property_field(), self.get_user_field()):
            if rel:
                rels.append(rel)
        return tuple(rels)

    # Колонки-коллбеки
    @admin.display(description="Объект")
    def property_col(self, obj):
        for name in ("property", "listing", "estate"):
            if hasattr(obj, name):
                return getattr(obj, name)
        return None

    @admin.display(description="Показатель")
    def metric_col(self, obj):
        for n in ("count", "search_count", "views", "views_count", "total", "score"):
            if hasattr(obj, n):
                return getattr(obj, n)
        return None

    @admin.display(description="Значение")
    def primary_col(self, obj):
        for n in ("query", "term", "title", "name", "keyword"):
            if hasattr(obj, n):
                return getattr(obj, n)
        return None

    @admin.display(description="Дата/период")
    def date_col(self, obj):
        for n in ("date", "day", "period", "created_at", "created", "last_used_at", "last_viewed_at"):
            if hasattr(obj, n):
                return getattr(obj, n)
        return None


# Регистрируем все модели из приложения analytics (или analitic) одной универсальной админкой
for app_label in ("analytics", "analitic"):
    try:
        cfg = apps.get_app_config(app_label)
    except LookupError:
        continue
    for model in cfg.get_models():
        # Можно переопределить для конкретных моделей при необходимости:
        # if model.__name__ == "SearchQuery": class SearchQueryAdmin(AnalyticsModelAdmin): ...
        try:
            admin.site.register(model, AnalyticsModelAdmin)
        except admin.sites.AlreadyRegistered:
            pass