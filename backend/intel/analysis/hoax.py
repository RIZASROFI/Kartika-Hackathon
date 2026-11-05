"""Analisis indikasi hoaks/misleading berbasis penanda struktur klaim.

Modul ini tidak melakukan pencocokan fakta eksternal. Skor hanya mencerminkan
kelemahan atribusi, sensasionalisme, dan tekanan untuk menyebarkan konten.
"""

from __future__ import annotations

import re

from intel.analysis.lexicons import (
    ABSOLUTE_TERMS,
    HEDGE_TERMS,
    OFFICIAL_SOURCE_PATTERN,
    SENSATIONAL_TERMS,
    TRACEABLE_ATTRIBUTION_TERMS,
    URGENCY_TERMS,
    VAGUE_ATTRIBUTION_TERMS,
)
from intel.analysis.text_stats import (
    VERDICT_HOAX_THRESHOLD,
    VERDICT_VERIFY_THRESHOLD,
    ClaimResult,
    SignalResult,
    count_hits,
    extract_claims,
    make_signal,
    words,
)

NUMERIC_CLAIM_RE = re.compile(
    # Penutup memakai (?!\w), bukan \b: "%" bukan karakter kata sehingga \b
    # membuat "100%" tidak pernah cocok.
    r"\b\d{1,3}(?:[.,]\d+)?\s?(%|persen|juta|miliar|triliun|ribu|orang|hari|tahun)(?!\w)",
    re.IGNORECASE,
)


def analyze_hoax(text: str, title: str | None = None) -> tuple[SignalResult, list[ClaimResult]]:
    corpus = f"{title or ''} {text}"
    word_total = max(1, len(words(corpus)))
    lowered = corpus.lower()

    traceable_hits, traceable_matched = count_hits(lowered, TRACEABLE_ATTRIBUTION_TERMS)
    vague_hits, vague_matched = count_hits(lowered, VAGUE_ATTRIBUTION_TERMS)
    hedge_hits, hedge_matched = count_hits(lowered, HEDGE_TERMS)
    official_hits = len(re.findall(OFFICIAL_SOURCE_PATTERN, lowered))
    sensational_hits, sensational_matched = count_hits(lowered, SENSATIONAL_TERMS)
    urgency_hits, urgency_matched = count_hits(lowered, URGENCY_TERMS)
    absolute_hits, absolute_matched = count_hits(lowered, ABSOLUTE_TERMS)
    numeric_hits = len(NUMERIC_CLAIM_RE.findall(corpus))

    score = 0.0
    details: list[str] = []

    # Atribusi dinilai dari sumber yang bisa dilacak, bukan dari kata "menurut"
    # yang juga dipakai hoax untuk berpura-pura memiliki sumber.
    if traceable_hits == 0:
        score += 20
        details.append(
            "Tidak ditemukan atribusi yang dapat ditelusuri (dilansir/pernyataan resmi/juru bicara)."
        )
    else:
        details.append(
            "Atribusi dapat ditelusuri: " + ", ".join(traceable_matched[:4]) + "."
        )

    if hedge_hits:
        score += min(27, hedge_hits * 9)
        details.append("Klaim bersandar pada sumber kabur: " + ", ".join(hedge_matched[:5]) + ".")

    if sensational_hits:
        score += min(18, sensational_hits * 6)
        details.append("Bahasa sensasional: " + ", ".join(sensational_matched[:5]) + ".")

    if urgency_hits:
        score += min(24, urgency_hits * 8)
        details.append("Dorongan menyebarkan segera: " + ", ".join(urgency_matched[:5]) + ".")

    if absolute_hits:
        score += min(10, absolute_hits * 4)
        details.append("Pernyataan absolut: " + ", ".join(absolute_matched[:5]) + ".")

    if numeric_hits and traceable_hits == 0:
        score += 12
        details.append(
            f"Memuat {numeric_hits} angka/statistik tanpa atribusi yang dapat ditelusuri."
        )

    if official_hits == 0 and (sensational_hits or urgency_hits or hedge_hits or numeric_hits):
        score += 10
        details.append("Tidak ada rujukan ke lembaga/sumber resmi yang dapat ditelusuri.")
    elif official_hits and traceable_hits == 0 and hedge_hits:
        # Pola otoritas semu: nama lembaga dipakai, tetapi tanpa pernyataan resmi.
        score += 10
        details.append(
            "Menyebut lembaga resmi tanpa pernyataan/kutipan resmi (pola otoritas semu)."
        )

    # Pengurang: hanya atribusi yang dapat ditelusuri yang menurunkan skor.
    if traceable_hits >= 2:
        score -= 12
        details.append("Beberapa atribusi dapat ditelusuri (mengurangi skor).")
    if official_hits >= 1 and not hedge_hits:
        score -= 8
        details.append("Menyebut lembaga resmi tanpa klaim bersumber kabur (mengurangi skor).")
    if vague_hits >= 2 and traceable_hits >= 1:
        score -= 6
        details.append("Atribusi dominan masih umum (mengurangi skor).")

    score = max(0.0, min(95.0, score))

    if score >= VERDICT_HOAX_THRESHOLD:
        explanation = (
            "Konten menunjukkan beberapa kelemahan informasi sekaligus: atribusi tidak jelas, "
            "tekanan menyebarkan, dan/atau klaim numerik tanpa sumber. Status: terindikasi "
            "hoax secara indikatif, bukan putusan fakta."
        )
    elif score >= VERDICT_VERIFY_THRESHOLD:
        explanation = (
            "Sebagian klaim belum didukung sumber yang dapat ditelusuri. Konten masuk kategori "
            "perlu verifikasi sebelum dipercaya atau dibagikan."
        )
    else:
        explanation = (
            "Tidak ditemukan indikasi kuat kelemahan informasi. Skor ini mengukur pola narasi, "
            "bukan kebenaran isi; status kebenaran dibaca dari panel Keputusan berbasis bukti."
        )

    confidence = 0.4
    confidence += 0.15 if word_total >= 150 else 0.05
    confidence += 0.1 if traceable_hits or official_hits else 0.0
    confidence += 0.1 if (sensational_hits + urgency_hits) >= 2 else 0.0

    signal = make_signal(
        category="hoax",
        title="Hoax & Fact-Checking Signal",
        score=score,
        confidence=confidence,
        explanation=explanation,
        details=details,
    )
    # Klaim diambil dari isi artikel saja: judul ikut dinilai pada sinyal, tetapi
    # menempelkan judul ke kalimat pertama membuat klaim menjadi rancu.
    return signal, extract_claims(text, signal.score)
