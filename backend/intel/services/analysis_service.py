"""Layanan pembuatan analisis dan penyimpanan temuan."""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import UTC, datetime
from urllib.parse import urlparse

from django.db import transaction
from django.utils import timezone

from intel.analysis.ebde import assess_evidence, build_evidence_items
from intel.analysis.pipeline import ENGINE_VERSION, apply_decision, run_analysis
from intel.analysis.text_stats import normalize_whitespace, word_count
from intel.models import (
    Analysis,
    AnalysisSignal,
    Claim,
    ContentItem,
    Evidence,
)
from intel.services.claim_match import (
    CLAIM_MATCH_LIMITATION,
    align_factcheck_hits,
)
from intel.services.claim_verification import (
    ClaimCheckResult,
    apply_claim_check_limitation,
    run_claim_verification,
)
from intel.services.extraction import ExtractedArticle, ExtractionError, extract_article
from intel.services.factcheck import FactCheckResult, apply_limitation, run_factcheck

logger = logging.getLogger(__name__)

SOCIAL_HOSTS = (
    "tiktok.com",
    "instagram.com",
    "instagr.am",
    "facebook.com",
    "fb.com",
    "fb.watch",
    "twitter.com",
    "x.com",
)


def _is_social_url(url: str) -> bool:
    """Deteksi tautan media sosial yang tidak dapat di-ingest otomatis."""
    host = (urlparse(url).hostname or "").casefold().rstrip(".")
    for prefix in ("www.", "m.", "mobile.", "web."):
        if host.startswith(prefix):
            host = host[len(prefix) :]
    return bool(host) and any(
        host == domain or host.endswith(f".{domain}") for domain in SOCIAL_HOSTS
    )


def _content_hash(text: str) -> str:
    return hashlib.sha256(normalize_whitespace(text).lower().encode("utf-8")).hexdigest()


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


def _persist_result(
    db_content: ContentItem,
    outcome,
    *,
    processing_ms: int,
    article_links: list[dict[str, str]] | None = None,
    created_at: datetime | None = None,
    factcheck: FactCheckResult | None = None,
    claim_check: ClaimCheckResult | None = None,
) -> Analysis:
    analysis = Analysis.objects.create(
        content=db_content,
        status="completed",
        engine_version=ENGINE_VERSION,
        model_used=outcome.model_used,
        verdict=outcome.verdict,
        risk_score=outcome.risk_score,
        risk_level=outcome.risk_level,
        confidence=outcome.confidence,
        summary=outcome.summary,
        limitations=outcome.limitations,
        factcheck=factcheck.to_json() if factcheck else {},
        claim_check=claim_check.to_json() if claim_check else {},
        decision=(
            outcome.decision.to_json() if getattr(outcome, "decision", None) else {}
        ),
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

    verifications = {
        item.claim: item for item in (claim_check.claims if claim_check else [])
    }
    verified_at = timezone.now() if claim_check and claim_check.status == "verified" else None
    Claim.objects.bulk_create(
        [
            Claim(
                analysis=analysis,
                text=claim.text,
                verdict=claim.verdict,
                rationale=claim.rationale,
                evidence_status=(
                    verifications[claim.text].status
                    if claim.text in verifications
                    else ""
                ),
                verification_note=(
                    verifications[claim.text].rationale
                    if claim.text in verifications
                    else ""
                ),
                citations=(
                    verifications[claim.text].citations
                    if claim.text in verifications
                    else []
                ),
                verified_at=verified_at if claim.text in verifications else None,
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

    # Hanya sumber yang benar-benar dikutip model yang disimpan sebagai bukti.
    cited_urls = {
        citation.get("url")
        for item in (claim_check.claims if claim_check else [])
        for citation in item.citations
        if citation.get("url")
    }
    stored_urls: set[str] = set()
    for item in claim_check.evidence if claim_check else []:
        if item.url not in cited_urls or item.url in stored_urls:
            continue
        stored_urls.add(item.url)
        Evidence.objects.create(
            analysis=analysis,
            title=item.title,
            url=item.url,
            publisher=item.publisher,
            kind="pencarian_web",
            snippet=item.snippet[:280] or None,
        )

    return analysis


def _analyze_content(
    content: ContentItem,
    *,
    article_links: list[dict[str, str]] | None = None,
    started_at: float | None = None,
    created_at: datetime | None = None,
    use_factcheck: bool = True,
    use_ai_check: bool = True,
) -> Analysis:
    pipeline_started = time.perf_counter()
    outcome = run_analysis(
        text=content.raw_text,
        title=content.title,
    )

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

    # Verifikasi klaim memanggil pencarian web + model bahasa, jadi juga di luar
    # transaksi dan tidak boleh menggagalkan analisis heuristik.
    claim_check: ClaimCheckResult | None = None
    if use_ai_check:
        claim_check = run_claim_verification(
            text=content.raw_text,
            title=content.title,
            claims=[claim.text for claim in outcome.claims],
        )
        outcome.limitations = apply_claim_check_limitation(
            outcome.limitations, claim_check.status
        )

    # Gerbang relevansi: temuan cek fakta hanya menimbang verdict bila membahas
    # pernyataan yang sama dengan konten. Model menilai kesetaraan klaim, bukan
    # benar/salah; bila model gagal, perilaku lama (kecocokan kata) dipakai.
    factcheck_hits = list(factcheck.hits) if factcheck else []
    alignment: dict[str, str] = {}
    alignment_status = "skipped"
    if factcheck_hits:
        alignment, alignment_status = align_factcheck_hits(
            text=content.raw_text,
            title=content.title,
            claims=[claim.text for claim in outcome.claims],
            hits=factcheck_hits,
        )
        if alignment_status == "applied":
            outcome.limitations = [CLAIM_MATCH_LIMITATION, *outcome.limitations]

    # Keputusan akhir: EBDE hanya menilai bukti eksternal. Sinyal narasi tetap
    # tersimpan sebagai risk_score dan tidak pernah diumpankan sebagai bukti.
    decision = assess_evidence(
        items=build_evidence_items(
            factcheck_hits=factcheck_hits,
            claim_results=claim_check.claims if claim_check else (),
            text=content.raw_text,
            title=content.title,
            factcheck_alignment=alignment,
        ),
        narrative_risk=outcome.risk_score,
        provider_status={
            "factcheck": factcheck.status if factcheck else "disabled",
            "claim_check": claim_check.status if claim_check else "disabled",
            "claim_match": alignment_status,
        },
    )
    outcome = apply_decision(outcome, decision)

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
            claim_check=claim_check,
        )

    logger.info(
        "analysis_created",
        extra={
            "extra_fields": {
                "analysis_id": str(analysis.id),
                "verdict": analysis.verdict,
                "risk_score": analysis.risk_score,
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
    source_type = "url" if url else "text"

    if url and _is_social_url(url):
        # Postingan media sosial hanya dapat dianalisis dari teks yang ditempel;
        # halaman aslinya berupa login wall atau shell JavaScript.
        raise ExtractionError(
            "Ingest otomatis postingan media sosial tidak tersedia. Salin teks "
            "atau caption postingan, lalu tempelkan pada mode Teks manual."
        )
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
        source_type=source_type,
        text=content_text,
        title=content_title,
        url=source_url,
        canonical_url=canonical_url,
        author=author,
        publisher=content_publisher,
        published_at=content_published_at,
        meta=meta,
    )

    return _analyze_content(
        content,
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
    return _analyze_content(
        content,
        created_at=published_at,
        use_factcheck=False,
        use_ai_check=False,
    )


def delete_analyses(analysis_ids: list[str]) -> int:
    """Hapus analisis beserta turunannya dan bersihkan konten yang jadi yatim.

    Konten yang masih dipakai analisis lain (mis. URL yang sama dianalisis ulang)
    sengaja dipertahankan agar statistik dan riwayat analisis tidak rusak.
    Mengembalikan jumlah analisis yang terhapus.
    """
    if not analysis_ids:
        return 0

    with transaction.atomic():
        queryset = Analysis.objects.filter(pk__in=analysis_ids)
        content_ids = set(queryset.values_list("content_id", flat=True))
        total = queryset.count()
        queryset.delete()
        if content_ids:
            ContentItem.objects.filter(
                pk__in=content_ids, analyses__isnull=True
            ).delete()
    return total

