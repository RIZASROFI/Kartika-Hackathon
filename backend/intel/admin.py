"""Konfigurasi Django admin untuk inspeksi data intelijen."""

from django.contrib import admin

from intel.models import (
    Analysis,
    AnalysisSignal,
    Claim,
    ContentItem,
    CoordinationLink,
    Evidence,
    FactCheckQuery,
)

admin.site.site_header = "KARTIKA Intel — Threat Intelligence"
admin.site.site_title = "KARTIKA Intel Admin"
admin.site.index_title = "Data Intelijen"


@admin.register(ContentItem)
class ContentItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "source_type",
        "title",
        "publisher",
        "word_count",
        "published_at",
        "ingested_at",
    )
    list_filter = ("source_type", "publisher", "language")
    search_fields = ("title", "publisher", "url", "raw_text")
    readonly_fields = (
        "id",
        "content_hash",
        "word_count",
        "ingested_at",
        "meta",
    )
    date_hierarchy = "ingested_at"


class ReadOnlyInline(admin.TabularInline):
    can_delete = False
    extra = 0

    def has_add_permission(self, request, obj=None):
        return False


class AnalysisSignalInline(ReadOnlyInline):
    model = AnalysisSignal
    fields = ("category", "title", "score", "level", "confidence", "details")
    readonly_fields = fields


class ClaimInline(ReadOnlyInline):
    model = Claim
    fields = ("text", "verdict", "rationale")
    readonly_fields = fields


class EvidenceInline(ReadOnlyInline):
    model = Evidence
    fields = ("kind", "title", "url", "publisher", "snippet", "retrieved_at")
    readonly_fields = fields


@admin.register(Analysis)
class AnalysisAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "content_title",
        "verdict",
        "risk_score",
        "risk_level",
        "confidence",
        "created_at",
    )
    list_filter = ("verdict", "risk_level", "engine_version")
    search_fields = ("content__title", "content__publisher", "summary", "id")
    date_hierarchy = "created_at"
    readonly_fields = (
        "id",
        "content",
        "status",
        "engine_version",
        "model_used",
        "verdict",
        "risk_score",
        "risk_level",
        "confidence",
        "summary",
        "limitations",
        "factcheck",
        "processing_ms",
        "created_at",
    )
    inlines = [AnalysisSignalInline, ClaimInline, EvidenceInline]

    @admin.display(description="Konten")
    def content_title(self, obj: Analysis) -> str:
        return obj.content.title or "(tanpa judul)"

    def has_add_permission(self, request):
        return False


@admin.register(CoordinationLink)
class CoordinationLinkAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "analysis",
        "related_analysis",
        "similarity",
        "hours_apart",
        "created_at",
    )
    search_fields = ("analysis__id", "related_analysis__id")
    list_filter = ("created_at",)
    readonly_fields = (
        "id",
        "analysis",
        "related_analysis",
        "similarity",
        "hours_apart",
        "shared_phrases",
        "created_at",
    )

    def has_add_permission(self, request):
        return False


@admin.register(FactCheckQuery)
class FactCheckQueryAdmin(admin.ModelAdmin):
    list_display = ("query_text", "provider", "hit_count", "created_at", "expires_at")
    list_filter = ("provider", "created_at")
    search_fields = ("query_text",)
    readonly_fields = (
        "id",
        "provider",
        "query_hash",
        "query_text",
        "payload",
        "hit_count",
        "created_at",
        "expires_at",
    )

    def has_add_permission(self, request):
        return False


# Signal, klaim, bukti, dan tautan dikelola otomatis oleh mesin analisis,
# jadi tidak didaftarkan sebagai menu admin terpisah.
