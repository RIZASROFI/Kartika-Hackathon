"""Pencocokan klaim temuan cek fakta dengan klaim yang diperiksa.

Model bahasa di sini **tidak** menilai benar atau salah. Tugasnya hanya satu:
apakah klaim yang diperiksa lembaga cek fakta membahas pernyataan yang sama
dengan konten. Hasilnya dipakai EBDE sebagai gerbang relevansi: temuan yang
membahas klaim lain disimpan sebagai konteks dan tidak menimbang verdict.

Pencarian MAFINDO memakai kata kunci tunggal, sehingga kecocokan kata tidak
cukup membuktikan kesamaan klaim: judul "[SALAH] PN Surakarta menyatakan ijazah
Jokowi palsu" berbagi kata dengan laporan "Jokowi bersaksi di PN Jakarta Timur",
tetapi pernyataannya berbeda. Semua kegagalan (model nonaktif, kuota, JSON
rusak) dikembalikan sebagai status, bukan exception, agar analisis tetap jalan.
"""

from __future__ import annotations

import logging

from django.conf import settings

from intel.analysis.text_stats import normalize_whitespace
from intel.services.llm import LLMError, call_json

logger = logging.getLogger(__name__)

ALIGNMENT_SAME = "sama"
ALIGNMENT_DIFFERENT = "berbeda"
ALIGNMENT_UNSURE = "tidak_jelas"
ALLOWED_ALIGNMENTS = {ALIGNMENT_SAME, ALIGNMENT_DIFFERENT, ALIGNMENT_UNSURE}

MAX_CONTENT_CHARS = 1200
MAX_CLAIM_CHARS = 300

CLAIM_MATCH_LIMITATION = (
    "Kesetaraan klaim temuan cek fakta dengan konten dinilai model bahasa; temuan yang "
    "membahas klaim berbeda tidak dihitung dalam verdict dan tetap wajib diperiksa analis."
)

SYSTEM_PROMPT = """Anda memeriksa kesetaraan pernyataan untuk platform intelijen informasi.
Tugas: tentukan apakah KLAIM PEMERIKSA FAKTA membahas pernyataan yang SAMA dengan KONTEN.

Aturan:
- "sama" hanya jika kedua teks menyatakan hal yang sama; pelaku, perbuatan, objek, tempat, dan waktu tidak bertentangan.
- "berbeda" jika topiknya mirip tetapi pernyataannya lain. Contoh: konten melaporkan seseorang bersaksi di pengadilan, sedangkan pemeriksa fakta membantah klaim bahwa pengadilan menyatakan ijazahnya palsu.
- "tidak_jelas" jika teks yang diberikan tidak cukup untuk memutuskan.
- Jangan menilai benar atau salah; nilai hanya kesetaraan pernyataan.
- Satu jawaban untuk setiap nomor klaim pemeriksa fakta.
- Balas hanya JSON valid tanpa markdown:
  {"matches":[{"index":1,"alignment":"sama","reason":"maksimal 15 kata"}]}
"""


def _build_prompt(*, text: str, title: str | None, claims: list[str], hits) -> str:
    claim_lines = (
        "\n".join(f"- {normalize_whitespace(claim)[:MAX_CLAIM_CHARS]}" for claim in claims[:4])
        or "(tidak ada klaim yang diekstrak)"
    )
    hit_lines = []
    for index, hit in enumerate(hits, start=1):
        claim = normalize_whitespace(
            str(getattr(hit, "claim", "") or getattr(hit, "title", "") or "")
        )[:MAX_CLAIM_CHARS]
        hit_lines.append(
            f"[{index}] Pemeriksa: {getattr(hit, 'publisher', '') or '-'} | "
            f"Rating: {getattr(hit, 'rating', '') or '-'}\n"
            f"    Klaim yang diperiksa: {claim or '-'}"
        )
    return (
        f"JUDUL KONTEN: {title or '(tanpa judul)'}\n\n"
        f"ISI KONTEN:\n{normalize_whitespace(text)[:MAX_CONTENT_CHARS]}\n\n"
        f"KLAIM YANG DIEKSTRAK DARI KONTEN:\n{claim_lines}\n\n"
        "KLAIM PEMERIKSA FAKTA:\n" + "\n".join(hit_lines)
    )


def _parse_alignments(payload: dict, hits) -> dict[str, str]:
    alignments: dict[str, str] = {}
    entries = payload.get("matches")
    if not isinstance(entries, list):
        return alignments
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        try:
            index = int(entry.get("index"))
        except (TypeError, ValueError):
            continue
        alignment = str(entry.get("alignment") or "").strip().casefold()
        if not 1 <= index <= len(hits) or alignment not in ALLOWED_ALIGNMENTS:
            continue
        url = str(getattr(hits[index - 1], "url", "") or "")
        if url:
            alignments[url] = alignment
    return alignments


def align_factcheck_hits(*, text: str, title: str | None, claims, hits) -> tuple[dict[str, str], str]:
    """Kembalikan (peta url→kesetaraan, status) tanpa pernah melempar error.

    Status: "applied", "disabled", "failed", atau "skipped" (tanpa temuan).
    Peta kosong berarti pemanggil memakai perilaku lama (kecocokan kata).
    """
    hits = [hit for hit in hits or () if getattr(hit, "url", "")]
    if not hits:
        return {}, "skipped"
    if not (
        settings.CLAIM_MATCH_ENABLED
        and settings.LLM_ENABLED
        and settings.LLM_API_KEY
        and settings.LLM_MODEL
    ):
        return {}, "disabled"

    try:
        payload = call_json(
            system=SYSTEM_PROMPT,
            user=_build_prompt(
                text=text,
                title=title,
                claims=[str(claim) for claim in claims or ()],
                hits=hits,
            ),
        )
        alignments = _parse_alignments(payload, hits)
    except LLMError as exc:
        logger.warning(
            "claim_match_failed",
            extra={"extra_fields": {"error": exc.message, "hits": len(hits)}},
        )
        return {}, "failed"
    except Exception as exc:  # pragma: no cover - jangan gagalkan analisis
        logger.warning(
            "claim_match_failed",
            extra={"extra_fields": {"error": type(exc).__name__, "hits": len(hits)}},
        )
        return {}, "failed"

    if not alignments:
        return {}, "failed"
    return alignments, "applied"
