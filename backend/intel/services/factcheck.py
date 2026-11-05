"""Pencarian pemeriksaan fakta eksternal (Google Fact Check Tools + MAFINDO).

Modul ini bersifat *retrieval*: ia hanya menanyakan apakah sebuah klaim sudah
pernah diperiksa lembaga pemeriksa fakta. Hasilnya tidak mengubah verdict
heuristik, melainkan dilampirkan sebagai bukti pendukung yang dapat diaudit.
Semua kegagalan jaringan/kuota ditangani sebagai status, bukan exception, agar
analisis tetap selesai saat API tidak tersedia.

Dua provider didukung: Google Fact Check Tools (klaim global) dan MAFINDO
Yudistira Public API v2 (basis data cek fakta Indonesia). Keduanya dijalankan
terpisah agar kegagalan salah satu tidak menghapus temuan yang lain.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import timedelta
from urllib.parse import urlparse

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

MAFINDO_PROVIDER = "mafindo"
MAFINDO_SEARCH_PATH = "/antihoax/search"
# Server MAFINDO memblokir User-Agent non-browser dan path dengan trailing
# slash (keduanya membalas HTTP 403), jadi keduanya dikunci di sini.
MAFINDO_USER_AGENT = "KARTIKA-Intel/0.1.0"
MAFINDO_MAX_KEYWORDS = 4
MAFINDO_FALLBACK_PUBLISHER = "MAFINDO"
URL_RE = re.compile(r"https?://[^\s,]+")
ENTITY_RE = re.compile(r"[A-Za-z]+|[0-9]+")
# Kata jabatan/generik: sering berhuruf kapital tetapi tidak membedakan klaim.
ROLE_WORDS = {
    "presiden",
    "menteri",
    "pemerintah",
    "pemerintahan",
    "wakil",
    "ketua",
    "bapak",
    "saudara",
    "saudari",
    "kalian",
    "semua",
    "follow",
}

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

TOKEN_RE = re.compile(r"[a-z]+|[0-9]+")
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
    provider: str = PROVIDER
    # True bila `url` hanya rujukan yang dikutip pemeriksa fakta, bukan artikel
    # pemeriksaannya sendiri (MAFINDO kadang tidak menyertakan tautan artikel).
    reference_only: bool = False

    def to_json(self) -> dict:
        return asdict(self)


@dataclass
class FactCheckResult:
    status: str
    queries: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    hits: list[FactCheckHit] = field(default_factory=list)
    providers: list[str] = field(default_factory=list)
    message: str | None = None
    checked_at: str = field(default_factory=lambda: timezone.now().isoformat())

    @property
    def provider(self) -> str:
        """Nama provider gabungan, dipertahankan agar klien lama tetap jalan."""
        return "+".join(self.providers)

    def to_json(self) -> dict:
        return {
            "provider": self.provider,
            "providers": self.providers,
            "status": self.status,
            "queries": self.queries,
            "keywords": self.keywords,
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
    """Token penting untuk pencocokan; angka dipertahankan karena sering jadi pembeda klaim.

    Contoh: "PPN 12 persen" dan "bansos Rp 5 juta" hanya cocok dengan pemeriksaan
    fakta yang menyebut angka yang sama, sehingga token seperti "12" atau "5" harus
    ikut dibandingkan meski lebih pendek dari MIN_TOKEN_LENGTH.
    """
    tokens: set[str] = set()
    for token in TOKEN_RE.findall(value.casefold()):
        if token.isdigit():
            tokens.add(token)
        elif len(token) >= MIN_TOKEN_LENGTH and token not in STOPWORDS:
            tokens.add(token)
    return tokens


def overlap_ratio(hit_text: str, source_tokens: set[str]) -> float:
    """Porsi kata penting klaim yang juga muncul di konten yang dianalisis."""
    hit_tokens = _tokens(hit_text)
    if not hit_tokens or not source_tokens:
        return 0.0
    return len(hit_tokens & source_tokens) / len(hit_tokens)


def is_relevant_hit(
    hit_text: str, *, query_tokens: set[str], source_tokens: set[str]
) -> bool:
    """Apakah klaim pemeriksa fakta membahas hal yang sama dengan konten.

    Diuji dari dua arah karena judul sering memuat kata kunci klaim, sedangkan isi
    konten panjang memuat istilah yang dipakai pemeriksa fakta. Angka diperlakukan
    sebagai penanda klaim terkuat: dua klaim berbeda jarang berbagi nominal/tahun
    yang sama, sehingga klaim yang menyebut angka hanya dicocokkan dengan angka sama.
    """
    threshold = settings.FACTCHECK_MIN_OVERLAP
    hit_tokens = _tokens(hit_text)
    if not hit_tokens:
        return False

    # Klaim dengan nominal/tahun/persentase berbeda (>= 2 digit) adalah klaim lain.
    hit_numbers = {token for token in hit_tokens if token.isdigit() and len(token) >= 2}
    context_numbers = {
        token
        for token in source_tokens | query_tokens
        if token.isdigit() and len(token) >= 2
    }
    if hit_numbers and not hit_numbers <= context_numbers:
        return False

    if overlap_ratio(hit_text, source_tokens) >= threshold:
        return True

    shared = hit_tokens & query_tokens
    if len(shared) < 2:
        return False

    # Judul dua-tiga kata tanpa satu pun angka terlalu umum untuk dicocokkan lewat kata.
    if len(query_tokens) < 4 and not any(token.isdigit() for token in shared):
        return False

    return len(shared) / len(query_tokens) >= threshold


def _query_hash(query: str, *, provider: str, method: str) -> str:
    raw = "|".join(
        (
            provider,
            method,
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


def _cached_payload(query: str, *, provider: str, method: str) -> dict | list | None:
    row = FactCheckQuery.objects.filter(
        query_hash=_query_hash(query, provider=provider, method=method),
        expires_at__gt=timezone.now(),
    ).first()
    return row.payload if row else None


def _cache_payload(
    query: str,
    payload: dict | list,
    *,
    provider: str,
    method: str,
    hit_count: int,
) -> None:
    ttl = timedelta(hours=max(1, settings.FACTCHECK_CACHE_TTL_HOURS))
    FactCheckQuery.objects.update_or_create(
        query_hash=_query_hash(query, provider=provider, method=method),
        defaults={
            "provider": provider,
            "query_text": query[:512],
            "payload": payload,
            "hit_count": hit_count,
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
    query_tokens = _tokens(query)
    hits: list[FactCheckHit] = []
    for claim_entry in payload.get("claims") or []:
        claim_text = normalize_whitespace(claim_entry.get("text") or "")
        if not claim_text:
            continue
        if not is_relevant_hit(
            claim_text, query_tokens=query_tokens, source_tokens=source_tokens
        ):
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


def _first_url(*values: object) -> str:
    for value in values:
        match = URL_RE.search(str(value or ""))
        if match:
            return match.group(0).rstrip(".,;)")
    return ""


def _host(url: str) -> str:
    host = (urlparse(url).hostname or "").casefold()
    return host[4:] if host.startswith("www.") else host


def _lowercase_tokens(text: str) -> set[str]:
    """Token yang ditulis huruf kecil di teks sumber: kata isi, bukan nama diri.

    Kapitalisasi dibaca dari teks yang dianalisis, bukan dari judul artikel cek
    fakta: judul hampir selalu Title Case sehingga tidak membedakan apa pun.
    """
    tokens: set[str] = set()
    for match in ENTITY_RE.finditer(text or ""):
        raw = match.group()
        token = raw.casefold()
        if (
            raw[0].islower()
            and len(token) >= MIN_TOKEN_LENGTH
            and token not in STOPWORDS
        ):
            tokens.add(token)
    return tokens


def _mafindo_article_url(item: dict, claim_url: str) -> tuple[str, bool]:
    """Tautan artikel cek fakta dan penanda rujukan.

    `claim_review.claim_url` kadang menunjuk sumber klaim yang diperiksa (mis.
    YouTube) alih-alih artikelnya. URL dengan host yang sama dengan
    `source_link` karena itu dilewati. Bila tidak ada artikel, `references`
    dipakai sebagai rujukan dan ditandai `reference_only` agar UI tidak
    menyebutnya sebagai halaman pemeriksaan fakta.
    """
    source_host = _host(str(item.get("source_link") or ""))
    claim_host = _host(claim_url)
    if claim_host and claim_host != source_host:
        return _first_url(claim_url), False
    return _first_url(item.get("references"), claim_url), True


def _is_relevant_mafindo_hit(
    hit_title: str,
    *,
    query_tokens: set[str],
    source_tokens: set[str],
    content_tokens: set[str],
) -> bool:
    """Relevansi MAFINDO: aturan umum ditambah syarat kata isi yang sama.

    Caption media sosial sering menyebut banyak tokoh, sehingga kecocokan yang
    hanya berupa nama diri (mis. "Prabowo" dan "Bahlil") menghasilkan artikel
    tentang klaim lain. Minimal satu kata isi dari teks sumber harus sama.
    """
    if not is_relevant_hit(
        hit_title, query_tokens=query_tokens, source_tokens=source_tokens
    ):
        return False
    shared = _tokens(hit_title) & (source_tokens | query_tokens)
    return bool(shared & content_tokens)


def _mafindo_keywords(text: str, *, limit: int = MAFINDO_MAX_KEYWORDS) -> list[str]:
    """Kata kunci satu kata untuk pencarian MAFINDO.

    Pencarian MAFINDO mencocokkan frasa utuh (`ekspor gas` cocok, `gas
    singapura` tidak), sehingga rangkaian beberapa kata hampir selalu kosong.
    Satu kata selalu berupa frasa yang sah. Nama diri (kata berhuruf kapital di
    tengah kalimat) didahulukan karena paling khas dan sering muncul di judul
    artikel cek fakta; sisanya diisi kata terpanjang tanpa kata fungsi.
    """
    words: list[str] = []
    entities: list[str] = []
    seen: set[str] = set()
    for match in ENTITY_RE.finditer(text):
        raw = match.group()
        token = raw.casefold()
        if token in seen or token.isdigit():
            continue
        if len(token) < MIN_TOKEN_LENGTH or token in STOPWORDS or token in ROLE_WORDS:
            continue
        previous = text[: match.start()].rstrip()
        at_sentence_start = not previous or previous[-1] in ".!?\n:;•-—\"'("
        seen.add(token)
        if raw[0].isupper() and not at_sentence_start:
            entities.append(token)
        else:
            words.append(token)
    entities.sort(key=len, reverse=True)
    words.sort(key=len, reverse=True)
    return (entities + words)[: max(1, limit)]


def _fetch_mafindo(*, method: str, value: str) -> list[dict]:
    """Panggil endpoint pencarian Yudistira. Dipisah agar mudah di-mock."""
    data = {
        "key": settings.MAFINDO_API_KEY,
        "method": method,
        "value": value,
        "limit": max(1, settings.MAFINDO_PAGE_SIZE),
    }
    url = f"{settings.MAFINDO_BASE_URL}{MAFINDO_SEARCH_PATH}"

    try:
        with httpx.Client(
            timeout=settings.MAFINDO_TIMEOUT_SECONDS,
            headers={"Accept": "application/json", "User-Agent": MAFINDO_USER_AGENT},
        ) as client:
            response = client.post(url, data=data)
    except httpx.HTTPError as exc:
        raise FactCheckError(
            f"Koneksi ke MAFINDO gagal: {exc.__class__.__name__}."
        ) from exc

    if response.status_code in {401, 403}:
        raise FactCheckError(
            "MAFINDO menolak permintaan "
            f"(HTTP {response.status_code}). Periksa API key Mafindo.",
            status_code=response.status_code,
        )
    if response.status_code == 429:
        raise FactCheckError(
            "Kuota MAFINDO habis (HTTP 429). Coba lagi nanti.", status_code=429
        )
    if response.status_code >= 400:
        raise FactCheckError(
            f"MAFINDO mengembalikan HTTP {response.status_code}.",
            status_code=response.status_code,
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise FactCheckError("Respons MAFINDO bukan JSON yang valid.") from exc

    # Kunci yang salah tidak memakai status HTTP error: body-nya string
    # "Access failed" dengan HTTP 200, jadi isi respons harus diperiksa.
    if isinstance(payload, str):
        raise FactCheckError(
            f"MAFINDO menolak permintaan: {payload}.", status_code=401
        )
    if not isinstance(payload, list):
        raise FactCheckError("Bentuk respons MAFINDO tidak dikenali.")
    return [item for item in payload if isinstance(item, dict)]


def _mafindo_rating(item: dict) -> tuple[str, str]:
    """Label dan status UI dari satu item MAFINDO.

    Dokumentasi menyebut status `1`/`2`, tetapi data nyata juga memuat label
    teks seperti "Salah" atau "Benar", jadi keduanya ditangani.
    """
    rating = normalize_whitespace(str(item.get("status") or ""))
    classification = normalize_whitespace(str(item.get("classification") or ""))
    if rating in {"1", "2"}:
        return ("Fakta", "fakta") if rating == "1" else ("Hoaks", "hoax")
    return (
        rating or classification or "Tanpa label",
        classify_rating(f"{rating} {classification}"),
    )


def _extract_mafindo_hits(
    items: list[dict],
    *,
    query: str,
    source_tokens: set[str],
    match_text: str | None = None,
) -> list[FactCheckHit]:
    """Petakan hasil MAFINDO menjadi hit; `query` hanya label kueri.

    `match_text` adalah teks yang dipakai menilai relevansi. Kueri MAFINDO
    berupa satu kata, sedangkan penilaian relevansi butuh seluruh klaim, jadi
    keduanya dipisah.
    """
    reference_text = match_text or query
    query_tokens = _tokens(reference_text)
    content_tokens = _lowercase_tokens(reference_text)
    hits: list[FactCheckHit] = []
    for item in items:
        title = normalize_whitespace(str(item.get("title") or ""))
        if not title:
            continue
        if not _is_relevant_mafindo_hit(
            title,
            query_tokens=query_tokens,
            source_tokens=source_tokens,
            content_tokens=content_tokens,
        ):
            continue

        reviews = item.get("claim_review")
        claim_url = ""
        if isinstance(reviews, list):
            for review in reviews:
                if isinstance(review, dict) and review.get("claim_url"):
                    claim_url = str(review["claim_url"])
                    break

        rating, status = _mafindo_rating(item)
        publisher = normalize_whitespace(str(item.get("authors") or ""))
        article_url, reference_only = _mafindo_article_url(item, claim_url)
        hits.append(
            FactCheckHit(
                claim=title[:500],
                rating=rating[:120],
                status=status,
                publisher=(publisher or MAFINDO_FALLBACK_PUBLISHER)[:256],
                url=article_url,
                reference_only=reference_only,
                title=title[:512],
                review_date=(str(item.get("tanggal") or "").strip() or None),
                query=query,
                provider=MAFINDO_PROVIDER,
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


def _active_providers() -> list[str]:
    providers: list[str] = []
    if settings.FACTCHECK_ENABLED:
        providers.append(PROVIDER)
    if settings.MAFINDO_ENABLED:
        providers.append(MAFINDO_PROVIDER)
    return providers


def _safe_cache(
    query: str,
    payload: dict | list,
    *,
    provider: str,
    method: str,
    hit_count: int,
) -> None:
    try:
        _cache_payload(
            query,
            payload,
            provider=provider,
            method=method,
            hit_count=hit_count,
        )
    except Exception:  # pragma: no cover - cache tidak boleh memblokir analisis
        logger.exception("factcheck_cache_write_failed")


def _google_hits(
    *, queries: list[str], source_tokens: set[str], failures: list[FactCheckError]
) -> tuple[list[FactCheckHit], bool]:
    """Kembalikan temuan Google dan apakah provider ini sempat menjawab."""
    hits: list[FactCheckHit] = []
    reached = False
    for query in queries:
        payload = _cached_payload(query, provider=PROVIDER, method="text")
        if payload is None:
            try:
                payload = _fetch_claims(query)
            except FactCheckError as exc:
                failures.append(exc)
                logger.warning(
                    "factcheck_failed",
                    extra={
                        "extra_fields": {
                            "provider": PROVIDER,
                            "query": query,
                            "error": exc.message,
                        }
                    },
                )
                continue
            _safe_cache(
                query,
                payload,
                provider=PROVIDER,
                method="text",
                hit_count=len(payload.get("claims") or []),
            )
        reached = True
        hits.extend(_extract_hits(payload, query=query, source_tokens=source_tokens))
    return hits, reached


def _mafindo_hits(
    *,
    text: str,
    title: str | None,
    match_text: str,
    source_tokens: set[str],
    failures: list[FactCheckError],
) -> tuple[list[FactCheckHit], bool, list[str]]:
    """Temuan MAFINDO, apakah provider ini sempat menjawab, dan kata kunci yang dipakai."""
    hits: list[FactCheckHit] = []
    reached = False
    # Satu kata kunci = satu request; jumlahnya dibatasi MAFINDO_MAX_QUERIES
    # agar kuota hemat.
    keywords = _mafindo_keywords(
        f"{title or ''} {text}",
        limit=max(1, settings.MAFINDO_MAX_QUERIES),
    )
    for keyword in keywords:
        payload = _cached_payload(
            keyword, provider=MAFINDO_PROVIDER, method="title"
        )
        if payload is None:
            try:
                payload = _fetch_mafindo(method="title", value=keyword)
            except FactCheckError as exc:
                failures.append(exc)
                logger.warning(
                    "mafindo_factcheck_failed",
                    extra={
                        "extra_fields": {
                            "provider": MAFINDO_PROVIDER,
                            "method": "title",
                            "query": keyword,
                            "error": exc.message,
                        }
                    },
                )
                continue
            _safe_cache(
                keyword,
                payload,
                provider=MAFINDO_PROVIDER,
                method="title",
                hit_count=len(payload),
            )
        reached = True
        hits.extend(
            _extract_mafindo_hits(
                payload,
                query=keyword,
                source_tokens=source_tokens,
                match_text=match_text,
            )
        )
    return hits, reached, keywords


def run_factcheck(
    *, text: str, title: str | None = None, claims: list[str] | None = None
) -> FactCheckResult:
    """Cari pemeriksaan fakta untuk judul/klaim utama. Tidak pernah melempar error."""
    providers = _active_providers()
    if not providers:
        return FactCheckResult(status="disabled")

    queries = _build_queries(text=text, title=title, claims=claims or [])
    if not queries:
        return FactCheckResult(
            status="no_match",
            providers=providers,
            message="Klaim terlalu pendek untuk dicari.",
        )

    source_tokens = _tokens(f"{title or ''} {text}") | _tokens(" ".join(queries))
    failures: list[FactCheckError] = []
    hits: list[FactCheckHit] = []
    reached_any = False

    if PROVIDER in providers:
        google_hits, google_reached = _google_hits(
            queries=queries, source_tokens=source_tokens, failures=failures
        )
        hits.extend(google_hits)
        reached_any = reached_any or google_reached

    keywords: list[str] = []
    if MAFINDO_PROVIDER in providers:
        mafindo_hits, mafindo_reached, keywords = _mafindo_hits(
            text=text,
            title=title,
            match_text=queries[0],
            source_tokens=source_tokens,
            failures=failures,
        )
        hits.extend(mafindo_hits)
        reached_any = reached_any or mafindo_reached

    hits = _dedupe(hits)
    if hits:
        return FactCheckResult(
            status="matched",
            queries=queries,
            keywords=keywords,
            hits=hits,
            providers=providers,
        )
    if failures and not reached_any:
        return FactCheckResult(
            status="unavailable",
            queries=queries,
            keywords=keywords,
            providers=providers,
            message=failures[0].message,
        )
    return FactCheckResult(
        status="no_match", queries=queries, keywords=keywords, providers=providers
    )


def apply_limitation(limitations: list[str] | None, status: str) -> list[str]:
    """Ganti catatan batasan tentang pemeriksaan fakta eksternal sesuai hasil."""
    text = FACTCHECK_LIMITATION.get(status, FACTCHECK_LIMITATION["off"])
    remaining = [
        item
        for item in (limitations or [])
        if item not in FACTCHECK_LIMITATION.values()
    ]
    return [text, *remaining]
