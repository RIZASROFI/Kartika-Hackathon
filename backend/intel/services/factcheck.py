"""Pencarian pemeriksaan fakta eksternal (Google Fact Check Tools API).

Modul ini bersifat *retrieval*: ia hanya menanyakan apakah sebuah klaim sudah
pernah diperiksa lembaga pemeriksa fakta. Hasilnya tidak mengubah verdict
heuristik, melainkan dilampirkan sebagai bukti pendukung yang dapat diaudit.
Semua kegagalan jaringan/kuota ditangani sebagai status, bukan exception, agar
analisis tetap selesai saat API tidak tersedia.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import timedelta

import httpx
from django.conf import settings
from django.utils import timezone

from intel.analysis.pipeline import FACTCHECK_LIMITATION
from intel.analysis.text_stats import normalize_whitespace
from intel.models import FactCheckQuery

logger = logging.getLogger(__name__)

PROVIDER = "google"
ENDPOINT = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
MAX_HITS = 5
MAX_QUERY_CHARS = 200
MIN_TOKEN_LENGTH = 4
DEFAULT_OVERLAP = 0.45

# Urutan penting: "tidak benar" harus dinilai sebelum "benar".
RATING_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "hoax",
        (
            "hoax",
            "hoaks",
            "false",
            "palsu",
            "salah",
            "keliru",
            "menyesatkan",
            "misleading",
            "tidak benar",
            "bukan fakta",
            "fabrikasi",
            "misinformasi",
            "disinformasi",
            "konspirasi",
            "conspiracy",
            "manipulasi",
            "distorsi",
            "unfounded",
            "debunk",
        ),
    ),
    (
        "sebagian_benar",
        (
            "sebagian",
            "partially",
            "partly",
            "half true",
            "setengah benar",
            "missing context",
            "kurang konteks",
            "konteks",
            "mixed",
            "mixture",
            "ambiguous",
        ),
    ),
    (
        "fakta",
        (
            "benar",
            "true",
            "fakta",
            "accurate",
            "akurat",
            "correct",
            "tepat",
            "valid",
            "verified",
            "terverifikasi",
            "mostly true",
        ),
    ),
)

TOKEN_RE = re.compile(r"[a-z0-9]+")
STOPWORDS = {
    "yang",
    "untuk",
    "dengan",
    "dari",
    "dalam",
    "kata",
    "kata-kata",
    "adalah",
    "akan",
    "tidak",
    "juga",
    "karena",
    "tetapi",
    "tapi",
    "pada",
    "para",
    "atau",
    "agar",
    "bisa",
    "dapat",
    "sudah",
    "belum",
    "masih",
    "ini",
    "itu",
    "the",
    "and",
    "that",
    "with",
    "this",
    "have",
    "from",
}


class FactCheckError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass
class FactCheckHit:
    claim: str
    rating: str
    status: str
    publisher: str
    url: str
    title: str
    review_date: str | None = None
    query: str = ""

    def to_json(self) -> dict:
        return asdict(self)


@dataclass
class FactCheckResult:
    status: str
    queries: list[str] = field(default_factory=list)
    hits: list[FactCheckHit] = field(default_factory=list)
    message: str | None = None
    provider: str = PROVIDER
    checked_at: str = field(default_factory=lambda: timezone.now().isoformat())

    def to_json(self) -> dict:
        return {
            "provider": self.provider,
            "status": self.status,
            "queries": self.queries,
            "checked_at": self.checked_at,
            "message": self.message,
            "hit_count": len(self.hits),
            "hits": [hit.to_json() for hit in self.hits],
        }


def classify_rating(rating: str | None) -> str:
    """Petakan textualRating bebas menjadi status yang stabil untuk UI."""
    normalized = (rating or "").casefold()
    if not normalized.strip():
        return "tidak_jelas"
    for status, keywords in RATING_RULES:
        for keyword in keywords:
            if keyword in normalized:
                return status
    return "tidak_jelas"


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in TOKEN_RE.findall(value.casefold())
        if len(token) >= MIN_TOKEN_LENGTH and token not in STOPWORDS
    }


def overlap_ratio(hit_text: str, source_tokens: set[str]) -> float:
    """Porsi kata penting klaim yang juga muncul di konten yang dianalisis."""
    hit_tokens = _tokens(hit_text)
    if not hit_tokens or not source_tokens:
        return 0.0
    return len(hit_tokens & source_tokens) / len(hit_tokens)


def _query_hash(query: str) -> str:
    raw = "|".join(
        (
            PROVIDER,
            (settings.FACTCHECK_LANGUAGE_CODE or "any").casefold(),
            normalize_whitespace(query).casefold(),
        )
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _build_queries(
    *, text: str, title: str | None, claims: list[str]
) -> list[str]:
    limit = max(1, settings.FACTCHECK_MAX_QUERIES)
    candidates: list[str] = []
    if title and len(title.strip().split()) >= 4:
        candidates.append(title.strip())
    candidates.extend(claim.strip() for claim in claims if claim and claim.strip())
    if not candidates:
        first_sentence = re.split(r"(?<=[.!?])\s+", normalize_whitespace(text))[0]
        candidates.append(first_sentence)

    queries: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        cleaned = normalize_whitespace(candidate)[:MAX_QUERY_CHARS].strip(" .,-–—")
        key = cleaned.casefold()
        if len(key) < 12 or key in seen:
            continue
        seen.add(key)
        queries.append(cleaned)
        if len(queries) >= limit:
            break
    return queries


def _cached_payload(query: str) -> dict | None:
    row = FactCheckQuery.objects.filter(
        query_hash=_query_hash(query), expires_at__gt=timezone.now()
    ).first()
    return row.payload if row else None


def _store_payload(query: str, payload: dict) -> None:
    ttl = timedelta(hours=max(1, settings.FACTCHECK_CACHE_TTL_HOURS))
    FactCheckQuery.objects.update_or_create(
        query_hash=_query_hash(query),
        defaults={
            "provider": PROVIDER,
            "query_text": query[:512],
            "payload": payload,
            "hit_count": len(payload.get("claims") or []),
            "created_at": timezone.now(),
            "expires_at": timezone.now() + ttl,
        },
    )


def _fetch_claims(query: str) -> dict:
    """Panggil endpoint Google. Dipisah agar mudah diganti/mock di pengujian."""
    params: dict[str, str | int] = {
        "query": query,
        "pageSize": max(1, settings.FACTCHECK_PAGE_SIZE),
        "key": settings.GOOGLE_FACTCHECK_API_KEY,
    }
    if settings.FACTCHECK_LANGUAGE_CODE:
        params["languageCode"] = settings.FACTCHECK_LANGUAGE_CODE

    try:
        with httpx.Client(timeout=settings.FACTCHECK_TIMEOUT_SECONDS) as client:
            response = client.get(ENDPOINT, params=params)
    except httpx.HTTPError as exc:
        raise FactCheckError(
            f"Koneksi ke layanan pemeriksaan fakta gagal: {exc.__class__.__name__}."
        ) from exc

    if response.status_code == 400:
        raise FactCheckError(
            "Google Fact Check Tools menolak permintaan (HTTP 400). Periksa API key.",
            status_code=400,
        )
    if response.status_code in {401, 403}:
        raise FactCheckError(
            "API key pemeriksaan fakta tidak valid atau API belum diaktifkan "
            f"(HTTP {response.status_code}).",
            status_code=response.status_code,
        )
    if response.status_code == 429:
        raise FactCheckError(
            "Kuota pemeriksaan fakta habis (HTTP 429). Coba lagi nanti.",
            status_code=429,
        )
    if response.status_code >= 400:
        raise FactCheckError(
            f"Layanan pemeriksaan fakta mengembalikan HTTP {response.status_code}.",
            status_code=response.status_code,
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise FactCheckError("Respons pemeriksaan fakta bukan JSON yang valid.") from exc
    return payload if isinstance(payload, dict) else {}


def _extract_hits(payload: dict, *, query: str, source_tokens: set[str]) -> list[FactCheckHit]:
    threshold = settings.FACTCHECK_MIN_OVERLAP
    hits: list[FactCheckHit] = []
    for claim_entry in payload.get("claims") or []:
        claim_text = normalize_whitespace(claim_entry.get("text") or "")
        if not claim_text:
            continue
        if overlap_ratio(claim_text, source_tokens) < threshold:
            continue
        for review in claim_entry.get("claimReview") or []:
            url = (review.get("url") or "").strip()
            publisher = normalize_whitespace(
                (review.get("publisher") or {}).get("name") or ""
            )
            rating = normalize_whitespace(review.get("textualRating") or "")
            hits.append(
                FactCheckHit(
                    claim=claim_text[:500],
                    rating=rating or "Tanpa label",
                    status=classify_rating(rating),
                    publisher=publisher[:256] or "Penerbit tidak diketahui",
                    url=url,
                    title=normalize_whitespace(review.get("title") or claim_text)[:512],
                    review_date=review.get("reviewDate"),
                    query=query,
                )
            )
    return hits


def _dedupe(hits: list[FactCheckHit]) -> list[FactCheckHit]:
    seen: set[str] = set()
    unique: list[FactCheckHit] = []
    for hit in hits:
        key = hit.url or f"{hit.claim}|{hit.rating}"
        if key in seen:
            continue
        seen.add(key)
        unique.append(hit)
    unique.sort(key=lambda hit: hit.review_date or "", reverse=True)
    return unique[:MAX_HITS]


def run_factcheck(
    *, text: str, title: str | None = None, claims: list[str] | None = None
) -> FactCheckResult:
    """Cari pemeriksaan fakta untuk judul/klaim utama. Tidak pernah melempar error."""
    if not settings.FACTCHECK_ENABLED:
        return FactCheckResult(status="disabled")

    queries = _build_queries(text=text, title=title, claims=claims or [])
    if not queries:
        return FactCheckResult(status="no_match", message="Klaim terlalu pendek untuk dicari.")

    source_tokens = _tokens(f"{title or ''} {text}") | _tokens(" ".join(queries))
    hits: list[FactCheckHit] = []
    errors: list[FactCheckError] = []

    for query in queries:
        payload = _cached_payload(query)
        if payload is None:
            try:
                payload = _fetch_claims(query)
            except FactCheckError as exc:
                errors.append(exc)
                logger.warning(
                    "factcheck_failed",
                    extra={"extra_fields": {"query": query, "error": exc.message}},
                )
                continue
            try:
                _store_payload(query, payload)
            except Exception:  # pragma: no cover - cache tidak boleh memblokir analisis
                logger.exception("factcheck_cache_write_failed")
        hits.extend(_extract_hits(payload, query=query, source_tokens=source_tokens))

    hits = _dedupe(hits)
    if hits:
        return FactCheckResult(status="matched", queries=queries, hits=hits)
    if errors and len(errors) == len(queries):
        return FactCheckResult(
            status="unavailable", queries=queries, message=errors[0].message
        )
    return FactCheckResult(status="no_match", queries=queries)


def apply_limitation(limitations: list[str] | None, status: str) -> list[str]:
    """Ganti catatan batasan tentang pemeriksaan fakta eksternal sesuai hasil."""
    text = FACTCHECK_LIMITATION.get(status, FACTCHECK_LIMITATION["off"])
    remaining = [
        item
        for item in (limitations or [])
        if item not in FACTCHECK_LIMITATION.values()
    ]
    return [text, *remaining]
