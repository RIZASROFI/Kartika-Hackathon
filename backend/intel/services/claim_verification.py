"""Verifikasi status klaim dengan pencarian web terbuka + model bahasa.

Alur: klaim → cuplikan sumber (Exa) → model bahasa menilai HANYA dari cuplikan
tersebut → sitasi divalidasi terhadap hasil retrieval. Status yang tidak punya
sitasi valid diturunkan menjadi "tidak_cukup_bukti", sehingga model tidak dapat
mengarang dukungan. Semua kegagalan dikembalikan sebagai status, bukan exception.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from django.conf import settings

from intel.analysis.text_stats import normalize_whitespace, sentences
from intel.services.llm import LLMError, call_json
from intel.services.web_search import SearchError, WebEvidence, search_web

logger = logging.getLogger(__name__)

PROVIDER = "exa"
MAX_CLAIM_CHARS = 500
MAX_FALLBACK_CHARS = 240

STATUS_DIDUKUNG = "didukung"
STATUS_DIBANTAH = "dibantah"
STATUS_TIDAK_CUKUP = "tidak_cukup_bukti"
ALLOWED_STATUSES = {STATUS_DIDUKUNG, STATUS_DIBANTAH, STATUS_TIDAK_CUKUP}

# Status hasil verifikasi klaim dan catatan batasannya untuk laporan analisis.
CLAIM_CHECK_LIMITATION = {
    "verified": (
        "Status klaim dinilai model bahasa dari cuplikan hasil pencarian web; model dapat "
        "salah membaca sumber, sehingga setiap sitasi wajib dibuka dan diperiksa analis."
    ),
    "no_evidence": (
        "Pencarian web tidak menemukan sumber yang dapat dipakai; status klaim hanya "
        "berasal dari sinyal internal."
    ),
    "unavailable": (
        "Pencarian web atau model bahasa tidak dapat dihubungi saat analisis dibuat; "
        "status klaim hanya berasal dari sinyal internal."
    ),
    "disabled": (
        "Verifikasi klaim berbasis AI tidak aktif (kunci API atau LLM_ENABLED belum "
        "diatur); status klaim hanya berasal dari sinyal internal."
    ),
}

SYSTEM_PROMPT = """Anda asisten verifikasi klaim untuk platform intelijen informasi.
Tugas: nilai setiap klaim HANYA dari cuplikan bukti yang diberikan.

Aturan:
- Jangan memakai pengetahuan di luar bukti yang diberikan.
- status "didukung" hanya jika bukti eksplisit menguatkan klaim.
- status "dibantah" hanya jika bukti eksplisit menyangkal klaim.
- Selain itu gunakan "tidak_cukup_bukti".
- citations hanya boleh berisi URL yang ada pada daftar bukti, disalin persis (maksimal 3).
- rationale dalam bahasa Indonesia, maksimal 40 kata, sebutkan bukti mana yang dipakai.
- Balas hanya JSON valid tanpa markdown dengan bentuk:
  {"claims":[{"index":1,"status":"didukung","rationale":"...","citations":["https://..."]}]}
"""


@dataclass
class ClaimVerification:
    claim: str
    status: str
    rationale: str
    citations: list[dict] = field(default_factory=list)


@dataclass
class ClaimCheckResult:
    status: str
    model: str | None = None
    message: str | None = None
    claims: list[ClaimVerification] = field(default_factory=list)
    evidence: list[WebEvidence] = field(default_factory=list)

    def to_json(self) -> dict:
        return {
            "provider": PROVIDER,
            "status": self.status,
            "model": self.model,
            "message": self.message,
            "claim_count": len(self.claims),
            "verified_count": sum(
                1 for item in self.claims if item.status != STATUS_TIDAK_CUKUP
            ),
            "evidence_count": len(self.evidence),
            "claims": [
                {
                    "claim": item.claim,
                    "status": item.status,
                    "rationale": item.rationale,
                    "citations": item.citations,
                }
                for item in self.claims
            ],
        }


def _fallback_query(*, text: str, title: str | None) -> str:
    """Bentuk kueri pencarian saat tidak ada klaim yang terekstrak.

    Judul adalah ringkasan paling padat; bila tidak ada, kalimat pertama dipakai
    agar pencarian sumber terbuka tetap berjalan untuk konten naratif.
    """
    heading = normalize_whitespace(title or "")
    if heading:
        return heading[:MAX_FALLBACK_CHARS]
    for sentence in sentences(text):
        cleaned = normalize_whitespace(sentence)
        if len(cleaned) >= 20:
            return cleaned[:MAX_FALLBACK_CHARS]
    return normalize_whitespace(text)[:MAX_FALLBACK_CHARS]


def _dedupe_evidence(items: list[WebEvidence]) -> list[WebEvidence]:
    seen: set[str] = set()
    unique: list[WebEvidence] = []
    for item in items:
        key = item.url.rstrip("/").casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def _build_prompt(*, title: str | None, claims: list[str], evidence: list[WebEvidence]) -> str:
    claim_lines = [f"{index}. {claim}" for index, claim in enumerate(claims, start=1)]
    evidence_lines: list[str] = []
    for index, item in enumerate(evidence, start=1):
        snippet = item.snippet or "(tidak ada cuplikan)"
        evidence_lines.append(
            f"[{index}] {item.publisher or 'sumber tidak dikenal'} — {item.title}\n"
            f"URL: {item.url}\n"
            f"Cuplikan: {snippet}"
        )
    return (
        f"JUDUL KONTEN: {title or '(tanpa judul)'}\n\n"
        "KLAIM YANG HARUS DINILAI:\n"
        + "\n".join(claim_lines)
        + "\n\nBUKTI HASIL PENCARIAN:\n"
        + "\n\n".join(evidence_lines)
    )


def _citation_index(evidence: list[WebEvidence]) -> dict[str, WebEvidence]:
    index: dict[str, WebEvidence] = {}
    for item in evidence:
        index[item.url] = item
        index[item.url.rstrip("/")] = item
    return index


def _validate(
    payload: dict,
    *,
    claims: list[str],
    evidence: list[WebEvidence],
) -> list[ClaimVerification]:
    by_url = _citation_index(evidence)
    raw_items = payload.get("claims")
    entries = raw_items if isinstance(raw_items, list) else []

    results: list[ClaimVerification] = []
    for position, claim in enumerate(claims, start=1):
        entry = next(
            (
                item
                for item in entries
                if isinstance(item, dict)
                and str(item.get("index", "")).strip() == str(position)
            ),
            None,
        )
        if entry is None:
            results.append(
                ClaimVerification(
                    claim=claim,
                    status=STATUS_TIDAK_CUKUP,
                    rationale="Model tidak memberi penilaian untuk klaim ini.",
                )
            )
            continue

        status = str(entry.get("status") or "").strip().casefold()
        if status not in ALLOWED_STATUSES:
            status = STATUS_TIDAK_CUKUP

        citations: list[dict] = []
        seen: set[str] = set()
        raw_citations = entry.get("citations")
        for url in raw_citations if isinstance(raw_citations, list) else []:
            key = str(url).strip()
            item = by_url.get(key) or by_url.get(key.rstrip("/"))
            if item is None or item.url in seen:
                continue
            seen.add(item.url)
            citations.append(
                {
                    "title": item.title,
                    "url": item.url,
                    "publisher": item.publisher,
                    "snippet": (item.snippet or "")[:280],
                    # Tanggal terbit dari hasil pencarian dipakai EBDE untuk
                    # menghitung kebaruan bukti, bukan nilai netral.
                    "published_date": item.published_date,
                }
            )
            if len(citations) >= max(1, settings.CLAIM_CHECK_MAX_CITATIONS):
                break

        rationale = str(entry.get("rationale") or "").strip()[:500]
        if not rationale:
            rationale = "Model tidak memberi alasan untuk penilaian ini."

        # Sitasi adalah syarat: tanpa sumber valid, klaim tidak boleh dinilai.
        if status != STATUS_TIDAK_CUKUP and not citations:
            status = STATUS_TIDAK_CUKUP
            rationale = (
                "Model tidak menyertakan sitasi yang cocok dengan hasil pencarian; "
                "klaim ditandai belum cukup bukti."
            )

        results.append(
            ClaimVerification(
                claim=claim,
                status=status,
                rationale=rationale,
                citations=citations,
            )
        )
    return results


def run_claim_verification(
    *, text: str, title: str | None = None, claims: list[str] | None = None
) -> ClaimCheckResult:
    """Nilai status klaim dari sumber terbuka. Tidak pernah melempar exception."""
    if not settings.AI_CLAIM_CHECK_ENABLED:
        return ClaimCheckResult(status="disabled")
    if not (settings.LLM_ENABLED and settings.LLM_API_KEY and settings.LLM_MODEL):
        return ClaimCheckResult(
            status="disabled",
            message=(
                "Aktifkan LLM_ENABLED dan isi LLM_API_KEY, LLM_MODEL, serta EXA_API_KEY "
                "untuk memakai verifikasi klaim berbasis AI."
            ),
        )
    if not settings.EXA_API_KEY:
        return ClaimCheckResult(
            status="disabled", message="API key pencarian web (EXA_API_KEY) belum diatur."
        )

    selected = [
        claim.strip()[:MAX_CLAIM_CHARS]
        for claim in (claims or [])
        if claim and claim.strip()
    ][: max(1, settings.CLAIM_CHECK_MAX_CLAIMS)]
    if not selected:
        # Tanpa klaim, pencarian tetap dijalankan memakai judul/kalimat pertama
        # agar konten naratif punya sumber terbuka yang dapat diaudit.
        fallback = _fallback_query(text=text, title=title)
        if not fallback:
            return ClaimCheckResult(status="no_claims")
        selected = [fallback]

    evidence: list[WebEvidence] = []
    errors: list[str] = []
    for claim in selected:
        try:
            evidence.extend(search_web(claim))
        except SearchError as exc:
            errors.append(exc.message)
            logger.warning(
                "claim_search_failed",
                extra={"extra_fields": {"claim": claim, "error": exc.message}},
            )

    if not evidence:
        return ClaimCheckResult(
            status="unavailable" if errors else "no_evidence",
            message=errors[0] if errors else None,
        )

    evidence = _dedupe_evidence(evidence)

    try:
        payload = call_json(
            system=SYSTEM_PROMPT,
            user=_build_prompt(title=title, claims=selected, evidence=evidence),
        )
    except LLMError as exc:
        logger.warning(
            "claim_llm_failed", extra={"extra_fields": {"error": exc.message}}
        )
        return ClaimCheckResult(
            status="unavailable", message=exc.message, evidence=evidence
        )

    return ClaimCheckResult(
        status="verified",
        model=settings.LLM_MODEL,
        claims=_validate(payload, claims=selected, evidence=evidence),
        evidence=evidence,
    )


def apply_claim_check_limitation(limitations: list[str] | None, status: str) -> list[str]:
    """Ganti catatan batasan verifikasi klaim sesuai status terbaru."""
    text = CLAIM_CHECK_LIMITATION.get(status)
    remaining = [
        item
        for item in (limitations or [])
        if item not in CLAIM_CHECK_LIMITATION.values()
    ]
    return [text, *remaining] if text else remaining
