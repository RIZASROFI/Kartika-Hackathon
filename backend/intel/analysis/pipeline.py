"""Orkestrasi mesin analisis KARTIKA Intel."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Sequence

from intel.analysis.bot import analyze_bot_signals
from intel.analysis.coordination import (
    CoordinationCandidate,
    CoordinationMatch,
    analyze_coordination,
)
from intel.analysis.hoax import analyze_hoax
from intel.analysis.provocation import analyze_provocation
from intel.analysis.text_stats import ClaimResult, SignalResult, risk_level, word_count

ENGINE_VERSION = "heuristic-1.0"
SIGNAL_WEIGHTS = {
    "hoax": 0.35,
    "provocation": 0.30,
    "coordination": 0.20,
    "bot_ai": 0.15,
}

FACTCHECK_LIMITATION = {
    "off": (
        "Tidak ada pencocokan otomatis ke basis data fakta eksternal; status klaim "
        "bersifat indikatif."
    ),
    "matched": (
        "Klaim ini pernah diperiksa lembaga pemeriksa fakta eksternal; temuan tersebut "
        "ditampilkan sebagai bukti pendukung, bukan pengganti penilaian analis."
    ),
    "no_match": (
        "Tidak ditemukan catatan pemeriksaan fakta eksternal untuk klaim ini; ketiadaan "
        "catatan bukan bukti kebenaran."
    ),
    "unavailable": (
        "Layanan pemeriksaan fakta eksternal tidak dapat dihubungi saat analisis dibuat; "
        "status klaim sepenuhnya bergantung pada sinyal internal."
    ),
}

VERDICT_LABELS = {
    "terkoordinasi": "Indikasi aktivitas terkoordinasi",
    "terindikasi_menyesatkan": "Terindikasi Hoax",
    "provokatif": "Provokatif",
    "perlu_verifikasi": "Perlu verifikasi",
    "risiko_rendah": "Terindikasi Fakta",
}


@dataclass
class Assessment:
    verdict: str
    risk_score: int
    risk_level: str
    confidence: float
    summary: str
    limitations: list[str]


@dataclass
class AnalysisOutcome:
    signals: list[SignalResult]
    claims: list[ClaimResult]
    matches: list[CoordinationMatch]
    verdict: str
    risk_score: int
    risk_level: str
    confidence: float
    summary: str
    limitations: list[str] = field(default_factory=list)
    corpus_size: int = 0


def _risk_score(signals: dict[str, SignalResult]) -> float:
    """Sinyal terkuat mendominasi, rata-rata berbobot memberi konteks."""
    total_weight = 0.0
    weighted_average = 0.0
    for category, weight in SIGNAL_WEIGHTS.items():
        signal = signals.get(category)
        if signal is None:
            continue
        weighted_average += signal.score * weight
        total_weight += weight
    weighted_average = weighted_average / total_weight if total_weight else 0.0
    strongest = max(signal.score for signal in signals.values())
    return strongest * 0.65 + weighted_average * 0.35


def _decide_verdict(
    signals: dict[str, SignalResult], matches: list[CoordinationMatch], risk_score: int
) -> str:
    hoax = signals["hoax"].score
    provocation = signals["provocation"].score
    coordination = signals["coordination"].score

    if len(matches) >= 2 and coordination >= 60:
        return "terkoordinasi"
    if hoax >= 60:
        return "terindikasi_menyesatkan"
    if provocation >= 60:
        return "provokatif"
    if hoax >= 35 or provocation >= 35 or coordination >= 50 or risk_score >= 25:
        return "perlu_verifikasi"
    return "risiko_rendah"


def _build_summary(
    *,
    verdict: str,
    risk_score: int,
    level: str,
    signals: dict[str, SignalResult],
    matches: list[CoordinationMatch],
    corpus_size: int,
) -> str:
    ordered = sorted(signals.values(), key=lambda signal: signal.score, reverse=True)
    primary = ordered[0]
    secondary = ordered[1]

    parts = [
        f"Skor risiko {risk_score}/100 ({level}). Status: {VERDICT_LABELS.get(verdict, verdict)}.",
        f"Sinyal tertinggi adalah {primary.title} ({primary.score}/100, {primary.level}), "
        f"diikuti {secondary.title} ({secondary.score}/100, {secondary.level}).",
    ]

    if matches:
        parts.append(
            f"Terdapat {len(matches)} konten dengan kemiripan narasi tinggi dalam jendela waktu, "
            "mengindikasikan amplifikasi pesan yang sama."
        )
    elif corpus_size:
        parts.append(
            "Tidak ada konten pembanding dengan kemiripan signifikan pada korpus saat ini."
        )

    if verdict == "terindikasi_menyesatkan":
        parts.append(
            "Kelemahan atribusi dan tekanan untuk menyebarkan membuat klaim perlu ditahan sebelum "
            "diviralkan. Cocokkan dengan sumber resmi terlebih dahulu."
        )
    elif verdict == "provokatif":
        parts.append(
            "Bahasa berpotensi memicu eskalasi. Rekomendasi: tunda distribusi dan tinjau konteks "
            "narasi secara utuh."
        )
    elif verdict == "terkoordinasi":
        parts.append(
            "Pola kemiripan dan kedekatan waktu menunjukkan amplifikasi terkoordinasi. "
            "Telusuri akun dan kanal penyebar utama."
        )
    elif verdict == "risiko_rendah":
        parts.append(
            "Tidak ada indikasi kuat pada sinyal yang tersedia, namun kebenaran isi tetap belum "
            "diverifikasi platform."
        )
    else:
        parts.append("Diperlukan verifikasi analis terhadap klaim dan konteks sebelum diambil tindakan.")

    return " ".join(parts)


def _build_limitations(corpus_size: int, min_corpus: int) -> list[str]:
    limitations = [
        FACTCHECK_LIMITATION["off"],
        "Sinyal bot/AI hanya memakai pola teks karena metadata aktivitas akun tidak tersedia.",
        "Analisis provokasi bergantung pada leksikon dan dapat melewatkan sarkasme atau konteks budaya.",
        "Semua hasil wajib ditinjau analis manusia sebelum dijadikan dasar tindakan.",
    ]
    if corpus_size < min_corpus:
        limitations.append(
            "Korpus pembanding masih kecil sehingga skor koordinasi belum reliabel."
        )
    return limitations


def assess_signals(
    signals: dict[str, SignalResult],
    matches: list[CoordinationMatch],
    *,
    corpus_size: int,
    min_corpus: int,
) -> Assessment:
    risk_score = int(round(_risk_score(signals)))
    level = risk_level(risk_score)
    verdict = _decide_verdict(signals, matches, risk_score)
    confidence = sum(
        signal.confidence * SIGNAL_WEIGHTS.get(category, 0.0)
        for category, signal in signals.items()
    )
    summary = _build_summary(
        verdict=verdict,
        risk_score=risk_score,
        level=level,
        signals=signals,
        matches=matches,
        corpus_size=corpus_size,
    )
    return Assessment(
        verdict=verdict,
        risk_score=risk_score,
        risk_level=level,
        confidence=round(confidence, 2),
        summary=summary,
        limitations=_build_limitations(corpus_size, min_corpus),
    )


def run_analysis(
    *,
    text: str,
    title: str | None,
    reference_time: datetime,
    candidates: Sequence[CoordinationCandidate] = (),
    threshold: float = 0.28,
    min_corpus: int = 3,
) -> AnalysisOutcome:
    if word_count(text) < 8:
        raise ValueError("Teks terlalu pendek untuk dianalisis (minimal 8 kata).")

    hoax_signal, claims = analyze_hoax(text, title)
    provocation_signal = analyze_provocation(text, title)
    bot_signal = analyze_bot_signals(text, title)
    coordination_result = analyze_coordination(
        text=text,
        title=title,
        reference_time=reference_time,
        candidates=candidates,
        threshold=threshold,
        min_corpus=min_corpus,
    )

    signals = {
        "hoax": hoax_signal,
        "provocation": provocation_signal,
        "coordination": coordination_result.signal,
        "bot_ai": bot_signal,
    }

    assessment = assess_signals(
        signals,
        coordination_result.matches,
        corpus_size=coordination_result.corpus_size,
        min_corpus=min_corpus,
    )

    return AnalysisOutcome(
        signals=[hoax_signal, provocation_signal, coordination_result.signal, bot_signal],
        claims=claims,
        matches=coordination_result.matches,
        verdict=assessment.verdict,
        risk_score=assessment.risk_score,
        risk_level=assessment.risk_level,
        confidence=assessment.confidence,
        summary=assessment.summary,
        limitations=assessment.limitations,
        corpus_size=coordination_result.corpus_size,
    )
