"""Layanan pembuatan analisis, korelasi koordinasi, dan penyimpanan temuan."""

from __future__ import annotations

import hashlib
import logging
import time
import uuid
from datetime import UTC, datetime, timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from intel.analysis.coordination import (
    CoordinationCandidate,
    CoordinationMatch,
    score_from_matches,
)
from intel.analysis.pipeline import ENGINE_VERSION, assess_signals, run_analysis
from intel.analysis.text_stats import SignalResult, normalize_whitespace, word_count
from intel.models import (
    Analysis,
    AnalysisSignal,
    Claim,
    ContentItem,
    CoordinationLink,
    Evidence,
)
from intel.services.extraction import ExtractedArticle, ExtractionError, extract_article
from intel.services.factcheck import FactCheckResult, apply_limitation, run_factcheck

logger = logging.getLogger(__name__)

DEFAULT_TITLE = "Konten tanpa judul"
MAX_CANDIDATES = 300


def _content_hash(text: str) -> str:
    return hashlib.sha256(normalize_whitespace(text).lower().encode("utf-8")).hexdigest()


def to_naive_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if timezone.is_aware(value):
        return timezone.make_naive(value, UTC)
    return value


def _as_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if timezone.is_naive(value):
        return timezone.make_aware(value, UTC)
    return value


def _get_or_create_content(
    *,
    source_type: str,
    text: str,
    title: str | None,
    url: str | None,
    canonical_url: str | None = None,
    author: str | None = None,
    publisher: str | None = None,
    published_at: datetime | None = None,
    meta: dict | None = None,
) -> ContentItem:
    normalized = normalize_whitespace(text)
    digest = _content_hash(normalized)
    existing = ContentItem.objects.filter(content_hash=digest).first()
    if existing is not None:
        return existing

    return ContentItem.objects.create(
        source_type=source_type,
        url=url,
        canonical_url=canonical_url,
        title=title,
        author=author,
        publisher=publisher,
        raw_text=normalized,
        content_hash=digest,
        word_count=word_count(normalized),
        published_at=_as_aware(published_at),
        meta=meta or {},
    )


def _load_candidates(
    *, exclude_content_id, reference_time: datetime
) -> tuple[list[CoordinationCandidate], int]:
    window_start = reference_time - timedelta(hours=settings.COORDINATION_WINDOW_HOURS)
    window_end = reference_time + timedelta(hours=settings.COORDINATION_WINDOW_HOURS)

    rows = list(
        Analysis.objects.select_related("content")
        .exclude(content_id=exclude_content_id)
        .order_by("-created_at")[:MAX_CANDIDATES]
    )

    candidates: list[CoordinationCandidate] = []
    seen_hashes: set[str] = set()
    for analysis in rows:
        content = analysis.content
        if content is None or content.content_hash in seen_hashes:
            continue
        reference = to_naive_utc(content.published_at or analysis.created_at)
        if reference is None or not (window_start <= reference <= window_end):
            continue
        seen_hashes.add(content.content_hash)
        candidates.append(
            CoordinationCandidate(
                analysis_id=str(analysis.id),
                title=content.title or DEFAULT_TITLE,
                text=content.raw_text,
                reference_time=reference,
            )
        )
    return candidates, len(candidates)


def _persist_result(
    db_content: ContentItem,
    outcome,
    *,
    processing_ms: int,
    article_links: list[dict[str, str]] | None = None,
    created_at: datetime | None = None,
    factcheck: FactCheckResult | None = None,
) -> Analysis:
    analysis = Analysis.objects.create(
        content=db_content,
        status="completed",
        engine_version=ENGINE_VERSION,
        verdict=outcome.verdict,
        risk_score=outcome.risk_score,
        risk_level=outcome.risk_level,
        confidence=outcome.confidence,
        summary=outcome.summary,
        limitations=outcome.limitations,
        factcheck=factcheck.to_json() if factcheck else {},
        processing_ms=processing_ms,
        created_at=_as_aware(created_at) or timezone.now(),
    )

    AnalysisSignal.objects.bulk_create(
        [
            AnalysisSignal(
                analysis=analysis,
                category=signal.category,
                title=signal.title,
                score=signal.score,
                level=signal.level,
                confidence=signal.confidence,
                explanation=signal.explanation,
                details=signal.details,
            )
            for signal in outcome.signals
        ]
    )

    Claim.objects.bulk_create(
        [
            Claim(
                analysis=analysis,
                text=claim.text,
                verdict=claim.verdict,
                rationale=claim.rationale,
            )
            for claim in outcome.claims
        ]
    )

    Evidence.objects.create(
        analysis=analysis,
        title=db_content.title or db_content.url or "Teks yang dikirim pengguna",
        url=db_content.url,
        publisher=db_content.publisher,
        kind="sumber_utama" if db_content.url else "input_pengguna",
        snippet=normalize_whitespace(db_content.raw_text)[:280],
    )
    for link in (article_links or [])[:5]:
        Evidence.objects.create(
            analysis=analysis,
            title=link.get("title") or link.get("url", ""),
            url=link.get("url"),
            kind="tautan",
        )
    for hit in (factcheck.hits if factcheck else [])[:5]:
        Evidence.objects.create(
            analysis=analysis,
            title=hit.title or hit.claim,
            url=hit.url or None,
            publisher=hit.publisher,
            kind="factcheck",
            snippet=f"{hit.rating} · {hit.claim}",
        )

    existing_pairs = set(
        CoordinationLink.objects.values_list("analysis_id", "related_analysis_id")
    )
    refreshed: set[uuid.UUID] = set()
    for match in outcome.matches:
        related_id = uuid.UUID(str(match.analysis_id))
        forward = (analysis.id, related_id)
        reverse = (related_id, analysis.id)
        if forward not in existing_pairs:
            CoordinationLink.objects.create(
                analysis_id=analysis.id,
                related_analysis_id=match.analysis_id,
                similarity=match.similarity,
                hours_apart=match.hours_apart,
                shared_phrases=match.shared_phrases,
            )
            existing_pairs.add(forward)
        if reverse not in existing_pairs:
            CoordinationLink.objects.create(
                analysis_id=related_id,
                related_analysis_id=analysis.id,
                similarity=match.similarity,
                hours_apart=match.hours_apart,
                shared_phrases=match.shared_phrases,
            )
            existing_pairs.add(reverse)
            refreshed.add(related_id)

    for related_id in refreshed:
        _refresh_coordination_scoring(related_id)

    return analysis


def _refresh_coordination_scoring(analysis_id) -> None:
    """Perbarui skor koordinasi konten lama saat konten baru yang mirip masuk."""
    analysis = (
        Analysis.objects.select_related("content")
        .prefetch_related("signals")
        .filter(pk=analysis_id)
        .first()
    )
    if analysis is None:
        return

    links = list(
        CoordinationLink.objects.filter(analysis_id=analysis_id).select_related(
            "related_analysis__content"
        )
    )
    if not links:
        return

    matches = [
        CoordinationMatch(
            analysis_id=str(link.related_analysis_id),
            title=(
                link.related_analysis.content.title
                if link.related_analysis and link.related_analysis.content
                else DEFAULT_TITLE
            )
            or DEFAULT_TITLE,
            similarity=link.similarity,
            hours_apart=link.hours_apart,
            shared_phrases=link.shared_phrases,
        )
        for link in links
    ]
    matches.sort(key=lambda match: match.similarity, reverse=True)

    corpus_size = Analysis.objects.count()
    coordination_signal = score_from_matches(
        matches=matches,
        corpus_size=corpus_size,
        min_corpus=settings.COORDINATION_MIN_CORPUS,
        threshold=settings.COORDINATION_SIMILARITY_THRESHOLD,
        best_similarity=matches[0].similarity,
    )

    signal_map = {signal.category: signal for signal in analysis.signals.all()}
    coordination_row = signal_map.get("coordination")
    if coordination_row is None:
        return

    coordination_row.score = coordination_signal.score
    coordination_row.level = coordination_signal.level
    coordination_row.confidence = coordination_signal.confidence
    coordination_row.explanation = coordination_signal.explanation
    coordination_row.details = coordination_signal.details
    coordination_row.save(
        update_fields=["score", "level", "confidence", "explanation", "details"]
    )

    signals = {
        category: SignalResult(
            category=signal.category,
            title=signal.title,
            score=signal.score,
            level=signal.level,
            confidence=signal.confidence,
            explanation=signal.explanation,
            details=signal.details,
        )
        for category, signal in signal_map.items()
    }
    assessment = assess_signals(
        signals,
        matches,
        corpus_size=corpus_size,
        min_corpus=settings.COORDINATION_MIN_CORPUS,
    )
    analysis.risk_score = assessment.risk_score
    analysis.risk_level = assessment.risk_level
    analysis.verdict = assessment.verdict
    analysis.confidence = assessment.confidence
    analysis.summary = assessment.summary
    factcheck_status = (analysis.factcheck or {}).get("status")
    analysis.limitations = (
        apply_limitation(assessment.limitations, factcheck_status)
        if factcheck_status
        else assessment.limitations
    )
    analysis.save(
        update_fields=[
            "risk_score",
            "risk_level",
            "verdict",
            "confidence",
            "summary",
            "limitations",
        ]
    )


def _analyze_content(
    content: ContentItem,
    *,
    reference_time: datetime,
    article_links: list[dict[str, str]] | None = None,
    started_at: float | None = None,
    created_at: datetime | None = None,
    use_factcheck: bool = True,
) -> Analysis:
    pipeline_started = time.perf_counter()
    candidates, corpus_size = _load_candidates(
        exclude_content_id=content.id, reference_time=reference_time
    )
    outcome = run_analysis(
        text=content.raw_text,
        title=content.title,
        reference_time=reference_time,
        candidates=candidates,
        threshold=settings.COORDINATION_SIMILARITY_THRESHOLD,
        min_corpus=settings.COORDINATION_MIN_CORPUS,
    )
    outcome.corpus_size = corpus_size

    # Pemeriksaan fakta eksternal dilakukan di luar transaksi: panggilan jaringan
    # tidak boleh menahan lock database, dan kegagalannya tidak membatalkan analisis.
    factcheck: FactCheckResult | None = None
    if use_factcheck:
        factcheck = run_factcheck(
            text=content.raw_text,
            title=content.title,
            claims=[claim.text for claim in outcome.claims],
        )
        if factcheck.status in {"matched", "no_match", "unavailable"}:
            outcome.limitations = apply_limitation(outcome.limitations, factcheck.status)

    processing_ms = int(
        (time.perf_counter() - (started_at or pipeline_started)) * 1000
    )

    with transaction.atomic():
        analysis = _persist_result(
            content,
            outcome,
            processing_ms=processing_ms,
            article_links=article_links,
            created_at=created_at,
            factcheck=factcheck,
        )

    logger.info(
        "analysis_created",
        extra={
            "extra_fields": {
                "analysis_id": str(analysis.id),
                "verdict": analysis.verdict,
                "risk_score": analysis.risk_score,
                "corpus_size": corpus_size,
                "processing_ms": processing_ms,
            }
        },
    )
    return analysis


def create_analysis(
    *,
    url: str | None = None,
    text: str | None = None,
    title: str | None = None,
    publisher: str | None = None,
    published_at: datetime | None = None,
) -> Analysis:
    started = time.perf_counter()
    article: ExtractedArticle | None = None
    meta: dict = {}

    if url:
        article = extract_article(url)
        content_text = article.text
        content_title = title or article.title
        content_publisher = publisher or article.publisher
        author = article.author
        content_published_at = published_at or article.published_at
        source_url = article.url
        canonical_url = article.canonical_url
        meta = {"outbound_link_count": len(article.links)}
    else:
        content_text = text or ""
        content_title = title
        content_publisher = publisher
        author = None
        content_published_at = published_at
        source_url = None
        canonical_url = None

    content = _get_or_create_content(
        source_type="url" if url else "text",
        text=content_text,
        title=content_title,
        url=source_url,
        canonical_url=canonical_url,
        author=author,
        publisher=content_publisher,
        published_at=content_published_at,
        meta=meta,
    )

    reference_time = to_naive_utc(content.published_at) or to_naive_utc(timezone.now())
    return _analyze_content(
        content,
        reference_time=reference_time,
        article_links=article.links if article else None,
        started_at=started,
    )


def analyze_text_local(
    *,
    text: str,
    title: str | None,
    publisher: str | None,
    published_at: datetime,
    meta: dict | None = None,
) -> Analysis:
    """Analisis teks tanpa jaringan, dipakai seeder dan pengujian."""
    content = _get_or_create_content(
        source_type="text",
        text=text,
        title=title,
        url=None,
        publisher=publisher,
        published_at=published_at,
        meta=meta or {},
    )
    reference_time = to_naive_utc(content.published_at) or to_naive_utc(timezone.now())
    return _analyze_content(
        content,
        reference_time=reference_time,
        created_at=published_at,
        use_factcheck=False,
    )
