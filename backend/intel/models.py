"""Model inti KARTIKA Intel."""

from __future__ import annotations

import uuid

from django.db import models
from django.utils import timezone


class ContentItem(models.Model):
    """Konten sumber yang dianalisis (teks manual atau artikel URL)."""

    SOURCE_TYPE_CHOICES = [("url", "URL artikel"), ("text", "Teks manual")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source_type = models.CharField(max_length=16, choices=SOURCE_TYPE_CHOICES)
    url = models.URLField(max_length=2048, blank=True, null=True)
    canonical_url = models.URLField(max_length=2048, blank=True, null=True)
    title = models.CharField(max_length=512, blank=True, null=True)
    author = models.CharField(max_length=256, blank=True, null=True)
    publisher = models.CharField(max_length=256, blank=True, null=True)
    language = models.CharField(max_length=8, default="id")
    raw_text = models.TextField()
    content_hash = models.CharField(max_length=64, unique=True)
    word_count = models.PositiveIntegerField(default=0)
    published_at = models.DateTimeField(blank=True, null=True)
    ingested_at = models.DateTimeField(default=timezone.now)
    meta = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "content_items"
        ordering = ["-ingested_at"]
        indexes = [models.Index(fields=["-ingested_at"], name="ix_content_ingested_at")]

    def __str__(self) -> str:
        return self.title or str(self.url) or f"Konten {self.id}"


class Analysis(models.Model):
    """Hasil penilaian satu konten."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content = models.ForeignKey(
        ContentItem, on_delete=models.CASCADE, related_name="analyses"
    )
    status = models.CharField(max_length=16, default="completed")
    engine_version = models.CharField(max_length=32, default="heuristic-1.0")
    model_used = models.CharField(max_length=64, blank=True, null=True)

    verdict = models.CharField(max_length=40, db_index=True)
    risk_score = models.PositiveSmallIntegerField(db_index=True)
    risk_level = models.CharField(max_length=16, db_index=True)
    confidence = models.FloatField(default=0.5)
    summary = models.TextField()
    limitations = models.JSONField(default=list, blank=True)
    factcheck = models.JSONField(default=dict, blank=True)
    processing_ms = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table = "analyses"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["-created_at"], name="ix_analyses_created_at")]

    def __str__(self) -> str:
        return f"{self.verdict} · {self.content}"


class AnalysisSignal(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    analysis = models.ForeignKey(
        Analysis, on_delete=models.CASCADE, related_name="signals"
    )
    category = models.CharField(max_length=24, db_index=True)
    title = models.CharField(max_length=160)
    score = models.PositiveSmallIntegerField()
    level = models.CharField(max_length=16)
    confidence = models.FloatField(default=0.5)
    explanation = models.TextField()
    details = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "analysis_signals"
        ordering = ["-score"]
        indexes = [models.Index(fields=["analysis", "category"], name="ix_signal_analysis_category")]

    def __str__(self) -> str:
        return f"{self.category}: {self.score}"


class Claim(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    analysis = models.ForeignKey(Analysis, on_delete=models.CASCADE, related_name="claims")
    text = models.TextField()
    verdict = models.CharField(max_length=40)
    rationale = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "claims"

    def __str__(self) -> str:
        return self.text[:80]


class Evidence(models.Model):
    KIND_CHOICES = [
        ("sumber_utama", "Sumber utama"),
        ("input_pengguna", "Input pengguna"),
        ("tautan", "Tautan referensi"),
        ("factcheck", "Pemeriksaan fakta"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    analysis = models.ForeignKey(Analysis, on_delete=models.CASCADE, related_name="evidence")
    title = models.CharField(max_length=512)
    url = models.URLField(max_length=2048, blank=True, null=True)
    publisher = models.CharField(max_length=256, blank=True, null=True)
    kind = models.CharField(max_length=24, choices=KIND_CHOICES, default="konteks")
    snippet = models.TextField(blank=True, null=True)
    retrieved_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "evidence"

    def __str__(self) -> str:
        return self.title[:80]


class FactCheckQuery(models.Model):
    """Cache respons fact-check API agar kuota hemat dan demo tetap jalan offline."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.CharField(max_length=24, default="google")
    query_hash = models.CharField(max_length=64, unique=True)
    query_text = models.CharField(max_length=512)
    payload = models.JSONField(default=dict, blank=True)
    hit_count = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        db_table = "factcheck_queries"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["expires_at"], name="ix_factcheck_expires_at")]

    def __str__(self) -> str:
        return self.query_text[:80]


class CoordinationLink(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    analysis = models.ForeignKey(
        Analysis, on_delete=models.CASCADE, related_name="links"
    )
    related_analysis = models.ForeignKey(
        Analysis, on_delete=models.CASCADE, related_name="incoming_links"
    )
    similarity = models.FloatField()
    hours_apart = models.FloatField(blank=True, null=True)
    shared_phrases = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "coordination_links"
        constraints = [
            models.UniqueConstraint(
                fields=["analysis", "related_analysis"], name="uq_coordination_pair"
            )
        ]
        indexes = [
            models.Index(fields=["analysis"], name="ix_link_analysis"),
            models.Index(fields=["related_analysis"], name="ix_link_related"),
        ]

    def __str__(self) -> str:
        return f"{self.analysis_id} ~ {self.related_analysis_id} ({self.similarity:.0%})"
