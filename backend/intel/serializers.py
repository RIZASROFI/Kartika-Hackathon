"""Serializer API KARTIKA Intel."""

from __future__ import annotations

from rest_framework import serializers

from intel.models import Analysis, AnalysisSignal, Claim, ContentItem, Evidence

DEFAULT_TITLE = "Konten tanpa judul"


class SignalOutSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnalysisSignal
        fields = (
            "id",
            "category",
            "title",
            "score",
            "level",
            "confidence",
            "explanation",
            "details",
        )
        read_only_fields = fields


class ClaimOutSerializer(serializers.ModelSerializer):
    class Meta:
        model = Claim
        fields = ("id", "text", "verdict", "rationale")
        read_only_fields = fields


class EvidenceOutSerializer(serializers.ModelSerializer):
    class Meta:
        model = Evidence
        fields = ("id", "title", "url", "publisher", "kind", "snippet", "retrieved_at")
        read_only_fields = fields


class ContentOutSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContentItem
        fields = (
            "source_type",
            "url",
            "title",
            "author",
            "publisher",
            "word_count",
            "published_at",
        )
        read_only_fields = fields


class AnalysisListItemSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    source_type = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()
    publisher = serializers.SerializerMethodField()

    class Meta:
        model = Analysis
        fields = (
            "id",
            "title",
            "verdict",
            "risk_score",
            "risk_level",
            "confidence",
            "summary",
            "source_type",
            "url",
            "publisher",
            "created_at",
        )
        read_only_fields = fields

    def get_title(self, obj: Analysis) -> str:
        return (obj.content.title if obj.content else None) or DEFAULT_TITLE

    def get_source_type(self, obj: Analysis) -> str:
        return obj.content.source_type if obj.content else "text"

    def get_url(self, obj: Analysis) -> str | None:
        return obj.content.url if obj.content else None

    def get_publisher(self, obj: Analysis) -> str | None:
        return obj.content.publisher if obj.content else None


class AnalysisDetailSerializer(AnalysisListItemSerializer):
    content = ContentOutSerializer(read_only=True)
    signals = SignalOutSerializer(many=True, read_only=True)
    claims = ClaimOutSerializer(many=True, read_only=True)
    evidence = EvidenceOutSerializer(many=True, read_only=True)
    related = serializers.SerializerMethodField()

    class Meta(AnalysisListItemSerializer.Meta):
        fields = (
            *AnalysisListItemSerializer.Meta.fields,
            "engine_version",
            "model_used",
            "processing_ms",
            "limitations",
            "factcheck",
            "content",
            "signals",
            "claims",
            "evidence",
            "related",
        )
        read_only_fields = fields

    def get_related(self, obj: Analysis) -> list[dict]:
        related = []
        for link in obj.links.all():
            target = link.related_analysis
            related.append(
                {
                    "id": str(link.related_analysis_id),
                    "title": (
                        target.content.title
                        if target and target.content and target.content.title
                        else DEFAULT_TITLE
                    ),
                    "verdict": target.verdict if target else "perlu_verifikasi",
                    "risk_score": target.risk_score if target else 0,
                    "similarity": link.similarity,
                    "hours_apart": link.hours_apart,
                    "shared_phrases": link.shared_phrases,
                }
            )
        return related


class AnalysisCreateSerializer(serializers.Serializer):
    url = serializers.CharField(
        required=False, allow_blank=True, max_length=2048, trim_whitespace=True
    )
    text = serializers.CharField(
        required=False, allow_blank=True, max_length=60_000, trim_whitespace=True
    )
    title = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, max_length=512
    )
    publisher = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, max_length=256
    )
    published_at = serializers.DateTimeField(required=False, allow_null=True)

    def validate(self, attrs: dict) -> dict:
        url = (attrs.get("url") or "").strip()
        text = (attrs.get("text") or "").strip()

        if not url and not text:
            raise serializers.ValidationError(
                "Kirimkan 'url' artikel atau 'text' untuk dianalisis."
            )
        if url and not url.startswith(("http://", "https://")):
            raise serializers.ValidationError("URL harus diawali http:// atau https://")
        if text and len(text.split()) < 8:
            raise serializers.ValidationError(
                "Teks minimal 8 kata agar analisis bermakna."
            )

        attrs["url"] = url or None
        attrs["text"] = text or None
        attrs["title"] = (attrs.get("title") or "").strip() or None
        attrs["publisher"] = (attrs.get("publisher") or "").strip() or None
        return attrs
