"""Evidence-Based Decision Engine (EBDE).

Modul ini adalah **satu-satunya** penentu verdict faktual. Masukannya hanya
bukti eksternal yang sudah dinormalisasi (hasil pemeriksaan fakta dan kutipan
sumber pencarian web), bukan sinyal narasi. Heuristik dan IndoBERT sengaja tidak
diperlakukan sebagai bukti: keduanya mengukur pola penulisan dan penyebaran,
bukan kebenaran isi.

Setiap bukti dinilai pada empat dimensi:

- relevansi   : kecocokan kata penting dua arah — porsi bukti yang muncul pada
                klaim/konten, atau porsi klaim yang dicakup bukti (dipakai yang
                terbaik agar artikel panjang tidak dihukum);
- kredibilitas: tingkat penerbit (lembaga cek fakta > media mapan > blog/UGC);
- kebaruan    : peluruhan eksponensial dengan paruh 365 hari;
- independensi: satu domain penerbit hanya dihitung sekali (bobot terkuatnya),
                sehingga sindikasi berita yang sama tidak menambah dukungan.

Verdict hanya diberikan bila bukti cukup: minimal dua domain independen, atau
satu temuan dari lembaga cek fakta dengan kredibilitas sangat tinggi. Selain itu
status tetap "Perlu Verifikasi" atau "Belum Dapat Dinilai" — mesin tidak
memaksakan kesimpulan.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from urllib.parse import urlparse

from intel.analysis.text_stats import normalize_whitespace

DECISION_ENGINE_VERSION = "ebde-1.0"

VERDICT_TERINDIKASI_FAKTA = "terindikasi_fakta"
VERDICT_TERINDIKASI_HOAKS = "terindikasi_hoaks"
VERDICT_CAMPURAN = "campuran"
VERDICT_PERLU_VERIFIKASI = "perlu_verifikasi"
VERDICT_BELUM_DAPAT_DINILAI = "belum_dapat_dinilai"

FACTUAL_VERDICT_LABELS = {
    VERDICT_TERINDIKASI_FAKTA: "Terindikasi Fakta",
    VERDICT_TERINDIKASI_HOAKS: "Terindikasi Hoaks",
    VERDICT_CAMPURAN: "Campuran",
    VERDICT_PERLU_VERIFIKASI: "Perlu Verifikasi",
    VERDICT_BELUM_DAPAT_DINILAI: "Belum Dapat Dinilai",
}

# Verdict lama (format heuristic-1.x) tetap dikenali agar riwayat dan data
# dashboard yang sudah ada tidak kehilangan label.
LEGACY_VERDICT_LABELS = {
    "terindikasi_menyesatkan": "Terindikasi Hoax (format lama)",
    "risiko_rendah": "Tanpa indikasi hoax (format lama)",
}

STANCE_SUPPORT = "mendukung"
STANCE_REFUTE = "membantah"
STANCE_PARTIAL = "sebagian"
STANCE_NEUTRAL = "netral"

# --- Ambang keputusan (sengaja eksplisit agar dapat diaudit) ---------------
MIN_DECISION_WEIGHT = 0.60  # bobot sisi pemenang minimal agar verdict diberikan
# Satu sisi yang didukung beberapa domain independen tanpa pembanding tetap
# dapat memutuskan walau bobot absolutnya di bawah MIN_DECISION_WEIGHT: yang
# menopang keputusan di sini adalah independensi, bukan besaran bobot semata.
UNCONTESTED_MIN_WEIGHT = 0.40
UNCONTESTED_MIN_GROUPS = 2
MIN_OPPOSING_WEIGHT = 0.30  # sisi lawan minimal agar dihitung sebagai konflik
DOMINANCE_RATIO = 0.70  # porsi sisi dominan terhadap dua sisi yang berlawanan
CONFLICT_RATIO = 0.50  # sisi lemah / sisi kuat minimal agar disebut campuran
MIN_INDEPENDENT_GROUPS = 2  # domain independen minimal untuk bukti dianggap cukup
# Pengecualian: satu temuan lembaga cek fakta boleh berdiri sendiri, tetapi
# hanya bila penerbitnya benar-benar kredibel dan temuannya relevan/baru.
SINGLE_SOURCE_MIN_CREDIBILITY = 0.90
SINGLE_SOURCE_MIN_RELEVANCE = 0.60
SINGLE_SOURCE_MIN_RECENCY = 0.50
PARTIAL_DOMINANT_WEIGHT = 0.50
RECENCY_HALF_LIFE_DAYS = 365.0
NEUTRAL_RECENCY = 0.60  # tanggal tidak diketahui: tidak dihukum berat

# --- Kredibilitas penerbit ------------------------------------------------
# Kunci dicocokkan sebagai substring pada "publisher + url" (casefold). Urutan
# penting: aturan pertama yang cocok dipakai.
CREDIBILITY_RULES: tuple[tuple[tuple[str, ...], float], ...] = (
    (
        (
            "youtube.com",
            "youtu.be",
            "tiktok.com",
            "facebook.com",
            "instagram.com",
            "x.com",
            "twitter.com",
            "blogspot.",
            "wordpress.com",
            "medium.com",
        ),
        0.30,
    ),
    (
        (
            "turnbackhoax",
            "mafindo",
            "cekfakta",
            "afp.com",
            "afpcekfakta",
            "factcheck.org",
            "snopes.com",
            "politifact.com",
            "fullfact.org",
            "reuters.com",
            "apnews.com",
        ),
        0.95,
    ),
    (
        (
            "tempo.co",
            "kompas.com",
            "cnnindonesia.com",
            "bbc.com",
            "bbc.co.uk",
            "antaranews.com",
            "katadata.co.id",
            "tirto.id",
            "nu.or.id",
            "theconversation.com",
        ),
        0.85,
    ),
    (
        (
            "kominfo.go.id",
            "bmkg.go.id",
            "bps.go.id",
            "setkab.go.id",
            "kemenkes.go.id",
            "kemensos.go.id",
            "who.int",
            "un.org",
            "worldbank.org",
            "europa.eu",
        ),
        0.90,
    ),
    (
        (
            # Domain pemerintah/kepolisian/akademik lain: lebih kredibel dari
            # blog, tetapi di bawah lembaga cek fakta dan media mapan.
            ".go.id",
            ".mil.id",
            ".polri.go.id",
            ".ac.id",
        ),
        0.80,
    ),
    (
        (
            "detik.com",
            "liputan6.com",
            "tribunnews.com",
            "cnbcindonesia.com",
            "suara.com",
            "republika.co.id",
            "kumparan.com",
            "idntimes.com",
        ),
        0.70,
    ),
)
DEFAULT_CREDIBILITY = 0.50

# Skor tertinggi yang mungkin diraih tiap dimensi. Dikirim ke UI agar angka
# seperti 0.85 dapat dibaca sebagai 0.85 dari 0.95, bukan dari 1.00 yang tidak
# mungkin dicapai karena tier kredibilitas tertinggi bernilai 0.95.
CREDIBILITY_MAX = max(score for _keywords, score in CREDIBILITY_RULES)
SCORE_MAX = {
    "relevance": 1.0,
    "credibility": CREDIBILITY_MAX,
    "recency": 1.0,
    "weight": round(CREDIBILITY_MAX, 2),
}

FACTCHECK_STANCES = {
    "hoax": STANCE_REFUTE,
    "fakta": STANCE_SUPPORT,
    "sebagian_benar": STANCE_PARTIAL,
}

CLAIM_STANCES = {
    "didukung": STANCE_SUPPORT,
    "dibantah": STANCE_REFUTE,
}

STANCE_LABELS = {
    STANCE_SUPPORT: "Mendukung klaim",
    STANCE_REFUTE: "Membantah klaim",
    STANCE_PARTIAL: "Sebagian benar",
    STANCE_NEUTRAL: "Belum jelas",
}

TOKEN_RE = re.compile(r"[a-z]+|[0-9]+")
MIN_TOKEN_LENGTH = 4
STOPWORDS = {
    "yang",
    "untuk",
    "dengan",
    "dari",
    "dalam",
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

DECISION_LIMITATION = (
    "Verdict ditetapkan Evidence-Based Decision Engine dari bukti eksternal "
    "(pemeriksaan fakta, kutipan sumber web) yang dinilai menurut relevansi, "
    "kredibilitas penerbit, kebaruan, dan independensi; mesin menahan diri bila "
    "bukti belum cukup."
)

# Gerbang kesetaraan klaim: temuan cek fakta untuk pernyataan lain bukan bukti.
ALIGNMENT_DIFFERENT = "berbeda"
CLAIM_MISMATCH_NOTE = (
    "Temuan cek fakta membahas klaim yang berbeda dari konten ini; dipakai sebagai "
    "konteks dan tidak dihitung dalam verdict."
)
CLAIM_MISMATCH_REASON = (
    "Semua temuan cek fakta membahas klaim yang berbeda dari konten ini, sehingga "
    "tidak ada bukti yang dapat menilai klaim tersebut."
)


def _tokens(value: str) -> set[str]:
    tokens: set[str] = set()
    for token in TOKEN_RE.findall((value or "").casefold()):
        if token.isdigit():
            tokens.add(token)
        elif len(token) >= MIN_TOKEN_LENGTH and token not in STOPWORDS:
            tokens.add(token)
    return tokens


def _overlap(text: str, reference: set[str]) -> float:
    """Porsi kata penting `text` yang juga muncul pada `reference`."""
    hit_tokens = _tokens(text)
    if not hit_tokens or not reference:
        return 0.0
    return len(hit_tokens & reference) / len(hit_tokens)


def _coverage(text: str, reference: set[str]) -> float:
    """Porsi kata penting `reference` yang tercakup oleh `text`.

    Kebalikan arah dari `_overlap`: dipakai agar artikel panjang yang benar-benar
    membahas klaim pendek tidak dihukum oleh snippetnya yang bertele-tele.
    """
    if not reference:
        return 0.0
    return len(_tokens(text) & reference) / len(reference)


def _parse_date(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def recency_score(value: object, *, now: datetime | None = None) -> float:
    """Skor 0–1 dengan paruh 365 hari; tanggal kosong memakai nilai netral."""
    parsed = _parse_date(value)
    if parsed is None:
        return NEUTRAL_RECENCY
    reference = now or datetime.now(UTC)
    age_days = (reference - parsed).days
    if age_days < 0:
        return 1.0
    return round(max(0.25, 0.5 ** (age_days / RECENCY_HALF_LIFE_DAYS)), 4)


def credibility_score(publisher: str | None, url: str | None = None) -> float:
    haystack = f"{publisher or ''} {url or ''}".casefold()
    for keywords, score in CREDIBILITY_RULES:
        if any(keyword in haystack for keyword in keywords):
            return score
    return DEFAULT_CREDIBILITY


def _domain(url: str | None) -> str:
    host = (urlparse(url or "").hostname or "").casefold()
    if host.startswith("www."):
        host = host[4:]
    return host


def independence_group(*, url: str | None, publisher: str | None) -> str:
    return _domain(url) or normalize_whitespace(publisher or "").casefold() or "tanpa-penerbit"


def canonical_url(url: str | None) -> str:
    parsed = urlparse(url or "")
    host = _domain(url)
    if not host:
        return normalize_whitespace(url or "").casefold()
    path = (parsed.path or "").rstrip("/")
    return f"{host}{path}".casefold() or host


@dataclass(frozen=True)
class EvidenceItem:
    """Satu bukti yang sudah dinilai. `weight` adalah hasil kali tiga dimensi."""

    title: str
    url: str
    publisher: str
    snippet: str
    stance: str
    kind: str
    provider: str
    relevance: float
    credibility: float
    recency: float
    group: str
    published_at: str | None = None
    note: str | None = None

    @property
    def weight(self) -> float:
        return round(self.relevance * self.credibility * self.recency, 4)

    def to_json(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "publisher": self.publisher,
            "snippet": self.snippet[:280],
            "stance": self.stance,
            "stance_label": STANCE_LABELS.get(self.stance, self.stance),
            "kind": self.kind,
            "provider": self.provider,
            "relevance": round(self.relevance, 3),
            "credibility": round(self.credibility, 3),
            "recency": round(self.recency, 3),
            "weight": self.weight,
            "group": self.group,
            "published_at": self.published_at,
            "note": self.note,
        }


def _dedupe(items: list[EvidenceItem]) -> list[EvidenceItem]:
    """Buang URL duplikat; pertahankan bobot tertinggi dan jenis terkuat."""
    best: dict[str, EvidenceItem] = {}
    for item in items:
        key = canonical_url(item.url) or normalize_whitespace(item.title).casefold()
        current = best.get(key)
        if current is None or item.weight > current.weight:
            best[key] = item
    return sorted(best.values(), key=lambda item: item.weight, reverse=True)


def build_evidence_items(
    *,
    factcheck_hits=(),
    claim_results=(),
    text: str = "",
    title: str | None = None,
    factcheck_alignment: dict[str, str] | None = None,
    now: datetime | None = None,
) -> list[EvidenceItem]:
    """Normalisasi temuan pemeriksaan fakta dan sitasi klaim menjadi bukti.

    Status model bahasa tidak dihitung sebagai bukti tersendiri: yang dinilai
    adalah **sumber yang dikutip**, dengan arah (mendukung/membantah) diambil
    dari status klaim. Dengan begitu satu sitasi tidak dihitung dua kali.
    """
    content_tokens = _tokens(f"{title or ''} {text}")
    items: list[EvidenceItem] = []

    for hit in factcheck_hits or ():
        stance = FACTCHECK_STANCES.get(str(getattr(hit, "status", "") or ""))
        if stance is None:
            continue
        hit_text = f"{getattr(hit, 'title', '')} {getattr(hit, 'claim', '')}"
        url = str(getattr(hit, "url", "") or "")
        publisher = str(getattr(hit, "publisher", "") or "")
        note = None
        if (factcheck_alignment or {}).get(url) == ALIGNMENT_DIFFERENT:
            # Temuan ini membahas pernyataan lain: simpan sebagai konteks,
            # jangan biarkan menimbang verdict sebagai bukti pendukung/pembantah.
            stance = STANCE_NEUTRAL
            note = CLAIM_MISMATCH_NOTE
        items.append(
            EvidenceItem(
                title=normalize_whitespace(str(getattr(hit, "title", "") or ""))[:512],
                url=url,
                publisher=publisher[:256],
                snippet=normalize_whitespace(
                    f"{getattr(hit, 'claim', '')} ({getattr(hit, 'rating', '')})"
                )[:500],
                stance=stance,
                kind="factcheck",
                provider=str(getattr(hit, "provider", "google") or "google"),
                # Hasil retrieval sudah lolos ambang relevansi; lantai 0,45
                # mencegah bukti yang benar-benar cocok terhukum oleh snippet pendek.
                relevance=round(max(0.45, _overlap(hit_text, content_tokens)), 3),
                credibility=credibility_score(publisher, url),
                recency=recency_score(getattr(hit, "review_date", None), now=now),
                group=independence_group(url=url, publisher=publisher),
                published_at=str(getattr(hit, "review_date", "") or "") or None,
                note=note,
            )
        )

    for result in claim_results or ():
        stance = CLAIM_STANCES.get(str(getattr(result, "status", "") or ""))
        if stance is None:
            continue
        claim_text = str(getattr(result, "claim", "") or "")
        claim_tokens = _tokens(claim_text) or content_tokens
        for citation in getattr(result, "citations", []) or []:
            if not isinstance(citation, dict):
                continue
            url = str(citation.get("url") or "")
            publisher = str(citation.get("publisher") or "")
            title_text = str(citation.get("title") or "")
            snippet = str(citation.get("snippet") or "")
            # Tanggal terbit boleh kosong pada hasil pencarian; bila ada, kebaruan
            # dihitung nyata, bila tidak tetap memakai nilai netral.
            published_at = str(citation.get("published_date") or "") or None
            items.append(
                EvidenceItem(
                    title=normalize_whitespace(title_text or url)[:512],
                    url=url,
                    publisher=publisher[:256],
                    snippet=normalize_whitespace(snippet)[:500],
                    stance=stance,
                    kind="pencarian_web",
                    provider="exa",
                    # Relevansi diambil dari arah terbaik: seberapa fokus bukti
                    # pada klaim, atau seberapa lengkap bukti menutup klaim.
                    relevance=round(
                        max(
                            0.35,
                            _overlap(f"{title_text} {snippet}", claim_tokens),
                            _coverage(f"{title_text} {snippet}", claim_tokens),
                        ),
                        3,
                    ),
                    credibility=credibility_score(publisher, url),
                    recency=recency_score(published_at, now=now),
                    group=independence_group(url=url, publisher=publisher),
                    published_at=published_at,
                )
            )

    return _dedupe(items)


@dataclass
class EvidenceDecision:
    verdict: str
    confidence: float
    rationale: str
    summary: str
    sufficient: bool = False
    insufficient_reason: str | None = None
    conflict: bool = False
    support_weight: float = 0.0
    refute_weight: float = 0.0
    partial_weight: float = 0.0
    support_groups: int = 0
    refute_groups: int = 0
    partial_groups: int = 0
    independent_groups: int = 0
    narrative_risk: int = 0
    items: list[EvidenceItem] = field(default_factory=list)
    provider_status: dict[str, str] = field(default_factory=dict)

    @property
    def label(self) -> str:
        return FACTUAL_VERDICT_LABELS.get(self.verdict, self.verdict)

    def to_json(self) -> dict:
        return {
            "engine": DECISION_ENGINE_VERSION,
            "verdict": self.verdict,
            "label": self.label,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "summary": self.summary,
            "sufficient": self.sufficient,
            "insufficient_reason": self.insufficient_reason,
            "conflict": self.conflict,
            "support_weight": self.support_weight,
            "refute_weight": self.refute_weight,
            "partial_weight": self.partial_weight,
            "support_groups": self.support_groups,
            "refute_groups": self.refute_groups,
            "partial_groups": self.partial_groups,
            "independent_groups": self.independent_groups,
            "item_count": len(self.items),
            "scales": dict(SCORE_MAX),
            "narrative_risk": self.narrative_risk,
            "provider_status": self.provider_status,
            "items": [item.to_json() for item in self.items],
        }


def _aggregate(items: list[EvidenceItem]):
    """Jumlahkan bobot per domain independen, bukan per artikel."""
    per_group: dict[str, dict[str, float]] = {}
    for item in items:
        bucket = per_group.setdefault(item.group, {})
        bucket[item.stance] = max(bucket.get(item.stance, 0.0), item.weight)

    def total(stance: str) -> float:
        return round(sum(bucket.get(stance, 0.0) for bucket in per_group.values()), 3)

    def groups(stance: str) -> int:
        return sum(1 for bucket in per_group.values() if bucket.get(stance, 0.0) > 0)

    return {
        STANCE_SUPPORT: (total(STANCE_SUPPORT), groups(STANCE_SUPPORT)),
        STANCE_REFUTE: (total(STANCE_REFUTE), groups(STANCE_REFUTE)),
        STANCE_PARTIAL: (total(STANCE_PARTIAL), groups(STANCE_PARTIAL)),
        "independent_groups": len(per_group),
    }


def _credible_single_source(items: list[EvidenceItem]) -> bool:
    """Satu temuan cek fakta kredibel boleh berdiri sendiri; artikel berita tidak."""
    return any(
        item.kind == "factcheck"
        and item.credibility >= SINGLE_SOURCE_MIN_CREDIBILITY
        and item.relevance >= SINGLE_SOURCE_MIN_RELEVANCE
        and item.recency >= SINGLE_SOURCE_MIN_RECENCY
        for item in items
    )


def _confidence(
    *, support: float, refute: float, partial: float, groups: int, sufficient: bool
) -> float:
    if not sufficient:
        return round(min(0.35, 0.15 + 0.05 * groups), 2)
    total = support + refute
    dominance = (max(support, refute) / total) if total else 0.0
    base = min(1.0, (support + refute + 0.5 * partial) / 1.8)
    return round(max(0.30, min(0.95, 0.30 + 0.45 * base + 0.20 * dominance)), 2)


def _no_evidence_reason(provider_status: dict[str, str]) -> str:
    factcheck = provider_status.get("factcheck")
    claim_check = provider_status.get("claim_check")
    if "unavailable" in {factcheck, claim_check}:
        return (
            "Layanan verifikasi tidak dapat dihubungi, sehingga tidak ada bukti yang "
            "dapat dinilai; status ditahan dan tidak ditebak."
        )
    if factcheck in {None, "disabled"} and claim_check in {None, "disabled"}:
        return (
            "Tidak ada layanan verifikasi fakta yang aktif, sehingga belum ada bukti "
            "eksternal untuk menilai klaim."
        )
    return (
        "Belum ada bukti eksternal yang terkumpul; ketiadaan catatan pemeriksaan "
        "fakta bukan bukti kebenaran."
    )


def assess_evidence(
    *,
    items: list[EvidenceItem] | tuple[EvidenceItem, ...] = (),
    narrative_risk: int = 0,
    provider_status: dict[str, str] | None = None,
) -> EvidenceDecision:
    """Tetapkan verdict faktual dari bukti. Tidak pernah memakai sinyal narasi."""
    status = dict(provider_status or {})
    unique = _dedupe(list(items))
    # Item netral (mis. temuan cek fakta untuk klaim lain) hanya konteks;
    # ia tidak boleh menambah domain independen maupun bobot keputusan.
    weighted = [item for item in unique if item.stance != STANCE_NEUTRAL]
    totals = _aggregate(weighted)

    support, support_groups = totals[STANCE_SUPPORT]
    refute, refute_groups = totals[STANCE_REFUTE]
    partial, partial_groups = totals[STANCE_PARTIAL]
    independent_groups = totals["independent_groups"]
    sufficient = bool(weighted) and (
        independent_groups >= MIN_INDEPENDENT_GROUPS
        or _credible_single_source(weighted)
    )
    both_sides = min(support, refute) / max(support, refute) if support and refute else 0.0
    conflict = (
        support >= MIN_OPPOSING_WEIGHT
        and refute >= MIN_OPPOSING_WEIGHT
        and both_sides >= CONFLICT_RATIO
    )
    dominance = (
        max(support, refute) / (support + refute) if (support + refute) else 0.0
    )

    insufficient_reason: str | None = None
    if not weighted:
        verdict = VERDICT_BELUM_DAPAT_DINILAI
        insufficient_reason = CLAIM_MISMATCH_REASON if unique else _no_evidence_reason(status)
        rationale = insufficient_reason
    elif not sufficient:
        verdict = VERDICT_PERLU_VERIFIKASI
        insufficient_reason = (
            f"Bukti baru berasal dari {independent_groups} domain independen dengan bobot "
            "terkuat di bawah ambang; EBDE tidak menetapkan status sebelum ada bukti pembanding."
        )
        rationale = insufficient_reason
    elif conflict:
        verdict = VERDICT_CAMPURAN
        rationale = (
            f"Bukti saling bertentangan: {support_groups} sumber mendukung (bobot {support:.2f}) "
            f"berhadapan dengan {refute_groups} sumber membantah (bobot {refute:.2f})."
        )
    elif support >= MIN_DECISION_WEIGHT and dominance >= DOMINANCE_RATIO:
        verdict = VERDICT_TERINDIKASI_FAKTA
        rationale = (
            f"{support_groups} sumber independen mendukung klaim (bobot {support:.2f}) "
            f"dengan dominasi {dominance:.0%}; bukti pembantah hanya {refute:.2f}."
        )
    elif refute >= MIN_DECISION_WEIGHT and dominance >= DOMINANCE_RATIO:
        verdict = VERDICT_TERINDIKASI_HOAKS
        rationale = (
            f"{refute_groups} sumber independen membantah klaim (bobot {refute:.2f}) "
            f"dengan dominasi {dominance:.0%}; bukti pendukung hanya {support:.2f}."
        )
    elif (
        refute >= UNCONTESTED_MIN_WEIGHT
        and refute_groups >= UNCONTESTED_MIN_GROUPS
        and support < MIN_OPPOSING_WEIGHT
    ):
        verdict = VERDICT_TERINDIKASI_HOAKS
        rationale = (
            f"{refute_groups} domain independen membantah klaim tanpa bukti pendukung yang "
            f"berarti (bobot {refute:.2f}); tidak ada temuan yang menyeimbangkan."
        )
    elif (
        support >= UNCONTESTED_MIN_WEIGHT
        and support_groups >= UNCONTESTED_MIN_GROUPS
        and refute < MIN_OPPOSING_WEIGHT
    ):
        verdict = VERDICT_TERINDIKASI_FAKTA
        rationale = (
            f"{support_groups} domain independen mendukung klaim tanpa bukti pembantah yang "
            f"berarti (bobot {support:.2f}); tidak ada temuan yang menyeimbangkan."
        )
    elif partial >= PARTIAL_DOMINANT_WEIGHT:
        verdict = VERDICT_CAMPURAN
        rationale = (
            f"Pemeriksaan fakta menilai klaim hanya sebagian benar (bobot sebagian {partial:.2f}); "
            "sebagian isi terbukti, sebagian tidak."
        )
    else:
        verdict = VERDICT_PERLU_VERIFIKASI
        rationale = (
            "Bukti terkumpul belum konvergen: tidak ada sisi yang cukup dominan untuk "
            "menetapkan status klaim."
        )

    confidence = _confidence(
        support=support,
        refute=refute,
        partial=partial,
        groups=independent_groups,
        sufficient=sufficient,
    )

    return EvidenceDecision(
        verdict=verdict,
        confidence=confidence,
        rationale=rationale,
        summary=(
            f"{FACTUAL_VERDICT_LABELS.get(verdict, verdict)} "
            f"(keyakinan bukti {confidence:.0%}). {rationale}"
        ),
        sufficient=sufficient,
        insufficient_reason=insufficient_reason,
        conflict=conflict,
        support_weight=support,
        refute_weight=refute,
        partial_weight=partial,
        support_groups=support_groups,
        refute_groups=refute_groups,
        partial_groups=partial_groups,
        independent_groups=independent_groups,
        narrative_risk=int(max(0, min(100, narrative_risk))),
        items=unique,
        provider_status=status,
    )
