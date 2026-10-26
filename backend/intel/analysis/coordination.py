"""Deteksi indikasi penyebaran narasi terkoordinasi antar konten tersimpan.

Pendekatan: Jaccard similarity atas shingle 4-kata, dibatasi jendela waktu.
Ini menangkap duplikasi/reproduksi narasi, bukan otomatisasi akun.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Sequence

from intel.analysis.text_stats import (
    SignalResult,
    jaccard,
    make_signal,
    normalize_whitespace,
    shingles,
    words,
)


@dataclass
class CoordinationCandidate:
    analysis_id: str
    title: str
    text: str
    reference_time: datetime


@dataclass
class CoordinationMatch:
    analysis_id: str
    title: str
    similarity: float
    hours_apart: float | None
    shared_phrases: list[str] = field(default_factory=list)


@dataclass
class CoordinationResult:
    signal: SignalResult
    matches: list[CoordinationMatch]
    corpus_size: int


def _similarity(left: str, right: str) -> float:
    size = 4 if min(len(words(left)), len(words(right))) >= 4 else 2
    return jaccard(shingles(left, size), shingles(right, size))


def _shared_phrases(left: str, right: str, limit: int = 4) -> list[str]:
    size = 4 if min(len(words(left)), len(words(right))) >= 4 else 2
    common = shingles(left, size) & shingles(right, size)
    ordered = sorted(common, key=lambda phrase: (-len(phrase), phrase))
    compact: list[str] = []
    for phrase in ordered:
        if any(phrase in existing for existing in compact):
            continue
        compact.append(phrase)
        if len(compact) >= limit:
            break
    return compact


def score_from_matches(
    *,
    matches: list[CoordinationMatch],
    corpus_size: int,
    min_corpus: int,
    threshold: float,
    best_similarity: float = 0.0,
) -> SignalResult:
    """Hitung skor koordinasi dari daftar pasangan yang sudah ditemukan."""
    details: list[str] = []

    if not matches:
        if corpus_size < min_corpus:
            score = min(20.0, best_similarity * 40)
            details.append(
                f"Korpus pembanding hanya {corpus_size} konten; minimal {min_corpus} untuk "
                "analisis yang bermakna."
            )
            explanation = (
                "Belum cukup konten pembanding dalam jendela waktu untuk menilai koordinasi. "
                "Skor rendah di sini berarti 'belum dapat dinilai', bukan 'bebas koordinasi'."
            )
            confidence = 0.25
        else:
            score = min(25.0, best_similarity * 50)
            details.append(
                f"Tidak ada konten lain dengan kemiripan di atas ambang {threshold:.0%} "
                f"(kemiripan tertinggi {best_similarity:.0%})."
            )
            explanation = (
                "Tidak ditemukan indikasi koordinasi berbasis kemiripan teks pada jendela waktu ini."
            )
            confidence = 0.5 if corpus_size >= 10 else 0.4
    else:
        score = min(
            100.0,
            max(match.similarity for match in matches) * 60 + min(30, len(matches) * 10),
        )
        if any(match.hours_apart is not None and match.hours_apart <= 12 for match in matches):
            score = min(100.0, score + 5)
        for match in matches[:4]:
            timing = (
                f", selisih {match.hours_apart:.1f} jam" if match.hours_apart is not None else ""
            )
            details.append(f"Kemiripan {match.similarity:.0%} dengan “{match.title}”{timing}.")
        explanation = (
            f"Ditemukan {len(matches)} konten dengan narasi sangat mirip dalam jendela waktu "
            "pengamatan. Ini indikasi amplifikasi/reproduksi narasi, bukan bukti aktor yang sama."
        )
        if corpus_size < min_corpus:
            details.append(
                f"Korpus pembanding masih kecil ({corpus_size} konten); keyakinan skor diturunkan."
            )
            confidence = 0.45
        else:
            confidence = 0.65 if corpus_size >= 10 else 0.55

    return make_signal(
        category="coordination",
        title="Coordinated Activity Analysis",
        score=score,
        confidence=confidence,
        explanation=explanation,
        details=details,
    )


def analyze_coordination(
    *,
    text: str,
    title: str | None,
    reference_time: datetime,
    candidates: Sequence[CoordinationCandidate],
    threshold: float,
    min_corpus: int,
) -> CoordinationResult:
    corpus = normalize_whitespace(f"{title or ''} {text}")
    matches: list[CoordinationMatch] = []
    best_similarity = 0.0

    for candidate in candidates:
        candidate_text = normalize_whitespace(f"{candidate.title} {candidate.text}")
        similarity = _similarity(corpus, candidate_text)
        best_similarity = max(best_similarity, similarity)
        if similarity < threshold:
            continue
        hours_apart: float | None = None
        if reference_time and candidate.reference_time:
            try:
                hours_apart = abs((reference_time - candidate.reference_time).total_seconds()) / 3600
            except TypeError:
                hours_apart = None
        matches.append(
            CoordinationMatch(
                analysis_id=candidate.analysis_id,
                title=candidate.title,
                similarity=round(similarity, 3),
                hours_apart=round(hours_apart, 1) if hours_apart is not None else None,
                shared_phrases=_shared_phrases(corpus, candidate_text),
            )
        )

    matches.sort(key=lambda match: match.similarity, reverse=True)
    matches = matches[:5]
    corpus_size = len(candidates)
    signal = score_from_matches(
        matches=matches,
        corpus_size=corpus_size,
        min_corpus=min_corpus,
        threshold=threshold,
        best_similarity=best_similarity,
    )
    return CoordinationResult(signal=signal, matches=matches, corpus_size=corpus_size)


def signal_from_result(result: CoordinationResult) -> SignalResult:
    return result.signal
