"""Analisis indikasi bahasa provokatif dan manipulatif."""

from __future__ import annotations

import re

from intel.analysis.lexicons import ESCALATION_PATTERN, PROVOCATION_GROUPS
from intel.analysis.text_stats import (
    SignalResult,
    caps_ratio,
    count_hits,
    exclamation_ratio,
    make_signal,
    words,
)

GROUP_LABELS = {
    "dehumanisasi": "Dehumanisasi",
    "kekerasan": "Ajakan kekerasan",
    "ajakan_makzul": "Ajakan penggulingan",
    "mobilisasi": "Mobilisasi massa",
    "kami_vs_mereka": "Polarisasi kami vs mereka",
    "ancaman": "Framing ancaman",
}


def analyze_provocation(text: str, title: str | None = None) -> SignalResult:
    corpus = f"{title or ''} {text}"
    word_total = max(1, len(words(corpus)))

    weighted = 0.0
    details: list[str] = []
    active_groups: list[str] = []

    for group, (weight, terms) in PROVOCATION_GROUPS.items():
        hits, matched = count_hits(corpus, terms)
        if hits == 0:
            continue
        active_groups.append(GROUP_LABELS[group])
        weighted += weight * min(hits, 3)
        details.append(f"{GROUP_LABELS[group]}: " + ", ".join(matched[:4]))

    # Normalisasi panjang: dokumen panjang wajar memuat lebih banyak kata pemicu.
    length_factor = min(1.0, (250 / word_total) ** 0.5)
    score = min(65.0, weighted * 5 * length_factor)
    structural = 0.0

    if word_total >= 25:
        caps = caps_ratio(corpus)
        if caps >= 0.45:
            structural += 18
            details.append(f"Proporsi huruf kapital sangat tinggi ({caps:.0%}).")
        elif caps >= 0.25:
            structural += 9
            details.append(f"Proporsi huruf kapital tinggi ({caps:.0%}).")

    exclaim = exclamation_ratio(corpus)
    if exclaim >= 2.0:
        structural += 10
        details.append(f"Kepadatan tanda seru tinggi ({exclaim:.1f} per 100 kata).")
    elif exclaim >= 0.8:
        structural += 4

    if re.search(ESCALATION_PATTERN, corpus.lower()):
        structural += 14
        details.append("Terdapat pola ajakan eskalasi (mis. 'ayo kita turunkan/serang').")

    score = min(100.0, score + structural)

    if not details:
        details.append("Tidak ada penanda leksikon provokasi yang cocok.")

    if score >= 50:
        explanation = (
            "Teks memuat penanda provokasi dominan pada kategori "
            + ", ".join(active_groups or ["struktur kalimat"])
            + ". Skor mengukur kekuatan sinyal bahasa, bukan niat pelaku."
        )
    elif score >= 25:
        explanation = (
            "Terdapat sebagian penanda provokasi, namun tidak konsisten. Perlu pembacaan "
            "konteks narasi secara utuh sebelum menarik kesimpulan."
        )
    else:
        explanation = (
            "Tidak ditemukan penanda provokasi yang kuat. Bahasa yang tenang tidak menjamin "
            "informasi akurat; tetap periksa klaim secara terpisah."
        )

    confidence = 0.45
    confidence += 0.15 if word_total >= 120 else 0.05
    if len(active_groups) >= 3:
        confidence += 0.1
    if weighted == 0:
        confidence -= 0.1

    return make_signal(
        category="provocation",
        title="Provocation Analysis",
        score=score,
        confidence=confidence,
        explanation=explanation,
        details=details,
    )
