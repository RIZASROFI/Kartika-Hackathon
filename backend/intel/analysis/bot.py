"""Sinyal otomatisasi dan konten AI yang dapat diamati dari teks saja.

Analisis ini tidak memiliki akses ke metadata akun, waktu unggah, atau
jaringan interaksi. Karena itu skor dibatasi dan diberi keyakinan rendah.
"""

from __future__ import annotations

import re

from intel.analysis.lexicons import AI_CONTENT_TERMS, TEMPLATE_PHRASES
from intel.analysis.text_stats import (
    HASHTAG_RE,
    MENTION_RE,
    SignalResult,
    count_hits,
    jaccard,
    make_signal,
    sentence_length_cv,
    sentences,
    shingles,
    words,
)


def analyze_bot_signals(text: str, title: str | None = None) -> SignalResult:
    corpus = f"{title or ''} {text}"
    token_total = max(1, len(words(corpus)))
    lowered = corpus.lower()

    score = 0.0
    details: list[str] = []

    ai_hits, ai_matched = count_hits(lowered, AI_CONTENT_TERMS)
    if ai_hits:
        score += min(45, ai_hits * 6)
        details.append("Frasa khas keluaran model bahasa: " + ", ".join(ai_matched[:5]) + ".")

    sequencing = sum(1 for term in ("pertama", "kedua", "ketiga") if term in lowered)
    if sequencing >= 2:
        score += 8
        details.append("Struktur enumerasi kaku (pertama/kedua/ketiga).")

    template_hits, template_matched = count_hits(lowered, TEMPLATE_PHRASES)
    if template_hits:
        score += min(20, template_hits * 6)
        details.append("Frasa templat promosi/spam: " + ", ".join(template_matched[:5]) + ".")

    hashtags = HASHTAG_RE.findall(corpus)
    if len(hashtags) >= 4:
        score += 18
        details.append(f"Kepadatan tagar tinggi ({len(hashtags)} tagar).")

    mentions = MENTION_RE.findall(corpus)
    if len(mentions) >= 3:
        score += 12
        details.append(f"Banyak penyebutan akun dalam satu konten ({len(mentions)}).")

    cv = sentence_length_cv(corpus)
    if token_total >= 60 and cv < 0.30:
        score += 12
        details.append(f"Panjang kalimat sangat seragam (CV {cv:.2f}); pola umum teks generatif.")

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if lines:
        listy = sum(1 for line in lines if re.match(r"^([-*•]|\d+[.)])\s", line))
        if len(lines) >= 5 and listy / len(lines) >= 0.5:
            score += 10
            details.append("Struktur daftar sangat rapi dan berulang.")

    sentence_list = sentences(text)
    if len(sentence_list) >= 4:
        duplicates = 0
        for index, sentence in enumerate(sentence_list):
            for other in sentence_list[index + 1 :]:
                if len(sentence) > 40 and jaccard(shingles(sentence, 3), shingles(other, 3)) > 0.8:
                    duplicates += 1
        if duplicates:
            score += min(15, duplicates * 7)
            details.append(f"Ditemukan {duplicates} pasangan kalimat yang hampir identik.")

    emoji_count = len(re.findall(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", corpus))
    if emoji_count >= 6:
        score += 8
        details.append(f"Penggunaan emoji berlebihan ({emoji_count}).")

    em_dash = corpus.count("—")
    if em_dash >= 3:
        score += 6
        details.append(f"Penggunaan em dash menonjol ({em_dash} kali).")

    if not details:
        details.append("Tidak ada sinyal otomatisasi/AI yang menonjol pada level teks.")

    # Dokumen panjang secara alami memuat lebih banyak frasa; turunkan bobotnya.
    score = min(75.0, score * min(1.0, (400 / token_total) ** 0.5))

    explanation = (
        "Sinyal dihitung dari pola teks saja, tanpa metadata akun atau riwayat unggahan. "
        "Hasil tidak dapat dijadikan bukti bahwa konten dibuat bot atau AI."
    )
    if score >= 50:
        explanation = (
            "Teks menunjukkan beberapa pola yang sering muncul pada konten otomatis, namun "
            "penyebabnya bisa editor manusia, templat redaksi, atau terjemahan. Diperlukan "
            "data aktivitas akun untuk konfirmasi."
        )

    confidence = 0.3
    if token_total >= 120:
        confidence += 0.1
    if len([detail for detail in details if "Tidak ada" not in detail]) >= 2:
        confidence += 0.1

    return make_signal(
        category="bot_ai",
        title="Bot & AI Content Signals",
        score=score,
        confidence=confidence,
        explanation=explanation,
        details=details,
    )
