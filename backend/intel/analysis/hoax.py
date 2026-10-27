"""Analisis indikasi hoaks/misleading berbasis penanda struktur klaim.

Modul ini tidak melakukan pencocokan fakta eksternal. Skor hanya mencerminkan
kelemahan atribusi, sensasionalisme, dan tekanan untuk menyebarkan konten.
"""

from __future__ import annotations

import re

from intel.analysis.lexicons import (
    ABSOLUTE_TERMS,
    ATTRIBUTION_TERMS,
    HEDGE_TERMS,
    OFFICIAL_SOURCE_PATTERN,
    SENSATIONAL_TERMS,
    URGENCY_TERMS,
)
from intel.analysis.text_stats import (
    ClaimResult,
    SignalResult,
    count_hits,
    extract_claims,
    make_signal,
    words,
)

NUMERIC_CLAIM_RE = re.compile(
    r"\b\d{1,3}(?:[.,]\d+)?\s?(%|persen|juta|miliar|triliun|ribu|orang|hari|tahun)\b",
    re.IGNORECASE,
)


def analyze_hoax(text: str, title: str | None = None) -> tuple[SignalResult, list[ClaimResult]]:
    corpus = f"{title or ''} {text}"
    word_total = max(1, len(words(corpus)))
    lowered = corpus.lower()

    attribution_hits, attribution_matched = count_hits(lowered, ATTRIBUTION_TERMS)
    official_hits = len(re.findall(OFFICIAL_SOURCE_PATTERN, lowered))
    sensational_hits, sensational_matched = count_hits(lowered, SENSATIONAL_TERMS)
    urgency_hits, urgency_matched = count_hits(lowered, URGENCY_TERMS)
    hedge_hits, hedge_matched = count_hits(lowered, HEDGE_TERMS)
    absolute_hits, absolute_matched = count_hits(lowered, ABSOLUTE_TERMS)
    numeric_hits = len(NUMERIC_CLAIM_RE.findall(corpus))

    score = 0.0
    details: list[str] = []

    if attribution_hits == 0 and word_total >= 40:
        score += 22
        details.append("Tidak ditemukan atribusi sumber (menurut/dilansir/pernyataan resmi).")
    elif attribution_hits:
        details.append("Atribusi disebutkan: " + ", ".join(attribution_matched[:4]) + ".")

    if official_hits == 0 and (numeric_hits or sensational_hits):
        score += 12
        details.append("Tidak ada rujukan ke lembaga/sumber resmi yang dapat ditelusuri.")

    if sensational_hits:
        score += min(18, sensational_hits * 6)
        details.append("Bahasa sensasional: " + ", ".join(sensational_matched[:5]) + ".")

    if urgency_hits:
        score += min(22, urgency_hits * 8)
        details.append("Dorongan menyebarkan segera: " + ", ".join(urgency_matched[:5]) + ".")

    if hedge_hits:
        score += min(18, hedge_hits * 7)
        details.append("Klaim berbasis sumber kabur: " + ", ".join(hedge_matched[:5]) + ".")

    if absolute_hits:
        score += min(10, absolute_hits * 4)
        details.append("Pernyataan absolut: " + ", ".join(absolute_matched[:5]) + ".")

    if numeric_hits and attribution_hits == 0:
        score += 12
        details.append(f"Memuat {numeric_hits} angka/statistik tanpa atribusi.")

    # Pengurang: teks yang secara eksplisit mengutip banyak sumber cenderung lebih sehat.
    if attribution_hits >= 2:
        score -= 12
        details.append("Beberapa atribusi sumber ditemukan (mengurangi skor).")
    if official_hits >= 1:
        score -= 8
        details.append("Menyebut lembaga resmi (mengurangi skor).")

    if not details:
        details.append("Tidak ada penanda kelemahan informasi yang menonjol.")

    score = max(0.0, min(95.0, score))

    if score >= 60:
        explanation = (
            "Konten menunjukkan beberapa kelemahan informasi sekaligus: atribusi tidak jelas, "
            "tekanan menyebarkan, dan/atau klaim numerik tanpa sumber. Status: terindikasi "
            "hoax secara indikatif, bukan putusan fakta."
        )
    elif score >= 35:
        explanation = (
            "Sebagian klaim belum didukung sumber yang dapat ditelusuri. Konten masuk kategori "
            "perlu verifikasi sebelum dipercaya atau dibagikan."
        )
    else:
        explanation = (
            "Tidak ditemukan indikasi kuat kelemahan informasi. Platform belum memverifikasi "
            "kebenaran isi, sehingga status klaim tetap belum diverifikasi."
        )

    confidence = 0.4
    confidence += 0.15 if word_total >= 150 else 0.05
    confidence += 0.1 if attribution_hits or official_hits else 0.0
    confidence += 0.1 if (sensational_hits + urgency_hits) >= 2 else 0.0

    signal = make_signal(
        category="hoax",
        title="Hoax & Fact-Checking Signal",
        score=score,
        confidence=confidence,
        explanation=explanation,
        details=details,
    )
    return signal, extract_claims(corpus, signal.score)
