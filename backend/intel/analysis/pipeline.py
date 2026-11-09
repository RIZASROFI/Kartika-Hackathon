"""Orkestrasi mesin analisis KARTIKA Intel.

Tiga tahap dipisah tegas:

1. **Analisis narasi** (modul ini): sinyal heuristik dan IndoBERT menghasilkan
   indeks pola narasi — pola atribusi, sensasionalisme, dan penyebaran. Tahap
   ini *tidak* menetapkan benar/salah.
2. **Verifikasi fakta** (`services/factcheck.py`, `services/claim_verification.py`):
   MAFINDO, Google Fact Check, Exa, dan model bahasa mengumpulkan bukti.
3. **Keputusan** (`analysis/ebde.py`): Evidence-Based Decision Engine menilai
   bukti dan menetapkan verdict faktual, terpisah dari risk score.

Karena verdict baru ada setelah bukti terkumpul, `run_analysis` mengembalikan
status sementara "Belum Dapat Dinilai" yang akan diganti
`ebde.apply_decision` / `analysis_service`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from intel.analysis import indobert
from intel.analysis.ebde import (
    DECISION_LIMITATION,
    FACTUAL_VERDICT_LABELS,
    LEGACY_VERDICT_LABELS,
    VERDICT_BELUM_DAPAT_DINILAI,
)
from intel.analysis.hoax import analyze_hoax
from intel.analysis.text_stats import (
    VERDICT_HOAX_THRESHOLD,
    VERDICT_VERIFY_THRESHOLD,
    ClaimResult,
    SignalResult,
    risk_level,
    word_count,
)

logger = logging.getLogger(__name__)

# 2.0: verdict dipindahkan dari heuristik ke Evidence-Based Decision Engine.
ENGINE_VERSION = "ebde-2.0"

VERDICT_LABELS = {**FACTUAL_VERDICT_LABELS, **LEGACY_VERDICT_LABELS}

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

MODEL_LIMITATION = (
    "Sinyal model IndoBERT dilatih pada korpus terbatas (TurnBackHoax sebagai kelas hoax, "
    "Tempo/CNN/Kompas sebagai kelas fakta) sehingga skornya peka terhadap gaya penulisan; "
    "skor ini ikut menimbang indeks pola narasi, tetapi tidak dipakai sebagai bukti "
    "kebenaran isi."
)

NARRATIVE_LIMITATION = (
    "Sinyal heuristik dan IndoBERT mengukur pola narasi (atribusi, sensasionalisme, gaya "
    "penulisan), bukan kebenaran isi; keduanya tidak menjadi bukti dalam keputusan akhir."
)


def _blend_risk_score(*, heuristic: float, model: float, weight: float) -> int:
    """Padukan skor heuristik dan model dengan bobot eksplisit, dibatasi 0..100."""
    blended = heuristic * (1.0 - weight) + model * weight
    return int(round(max(0.0, min(100.0, blended))))


def _blend_limitation(weight: float) -> str:
    return (
        "Indeks pola narasi memadukan sinyal heuristik dan IndoBERT "
        f"(bobot model {weight:.0%}); model peka terhadap gaya penulisan, sehingga skor "
        "dapat berubah tanpa perubahan kebenaran isi."
    )


@dataclass
class Assessment:
    """Penilaian narasi. `verdict` di sini bersifat indikatif dan tidak final."""

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
    verdict: str
    risk_score: int
    risk_level: str
    confidence: float
    summary: str
    limitations: list[str] = field(default_factory=list)
    model_used: str | None = None
    narrative_verdict: str | None = None
    decision: object | None = None


def _decide_narrative_verdict(hoax_score: int) -> str:
    if hoax_score >= VERDICT_HOAX_THRESHOLD:
        return "terindikasi_menyesatkan"
    if hoax_score >= VERDICT_VERIFY_THRESHOLD:
        return "perlu_verifikasi"
    return "risiko_rendah"


def _build_narrative_summary(
    *,
    risk_score: int,
    signal: SignalResult,
) -> str:
    """Ringkasan narasi tanpa status akhir — status ditetapkan EBDE."""
    return (
        f"Indeks pola narasi {risk_score}/100 mengukur pola penyebaran dan kelemahan "
        f"atribusi, bukan kebenaran isi maupun tingkat keamanan konten. Sinyal "
        f"{signal.title} mencatat {signal.score}/100."
    )


def _build_limitations() -> list[str]:
    return [
        FACTCHECK_LIMITATION["off"],
        NARRATIVE_LIMITATION,
        "Semua hasil wajib ditinjau analis manusia sebelum dijadikan dasar tindakan.",
    ]


def assess_signals(signals: dict[str, SignalResult]) -> Assessment:
    """Penilaian narasi murni: hanya sinyal heuristik yang dipakai.

    Sinyal model IndoBERT (bila aktif) disimpan terpisah dan tidak masuk ke
    fungsi ini. Verdict yang dikembalikan bersifat indikatif, bukan verdict
    faktual — lihat `ebde.assess_evidence`.
    """
    signal = signals["hoax"]
    risk_score = signal.score
    level = risk_level(risk_score)
    verdict = _decide_narrative_verdict(risk_score)
    summary = _build_narrative_summary(
        risk_score=risk_score,
        signal=signal,
    )
    return Assessment(
        verdict=verdict,
        risk_score=risk_score,
        risk_level=level,
        confidence=signal.confidence,
        summary=summary,
        limitations=_build_limitations(),
    )


def _model_signal(text: str, title: str | None) -> SignalResult | None:
    """Sinyal model untuk komponen skor; kegagalan tidak boleh menjatuhkan analisis."""
    try:
        return indobert.analyze_with_model(text, title)
    except Exception as exc:  # noqa: BLE001 - sinyal opsional tidak memutus pipeline
        logger.warning(
            "indobert_signal_skipped", extra={"extra_fields": {"error": str(exc)}}
        )
        return None


def run_analysis(*, text: str, title: str | None) -> AnalysisOutcome:
    if word_count(text) < 8:
        raise ValueError("Teks terlalu pendek untuk dianalisis (minimal 8 kata).")

    hoax_signal, claims = analyze_hoax(text, title)
    assessment = assess_signals({"hoax": hoax_signal})
    signals = [hoax_signal]
    limitations = list(assessment.limitations)
    risk_score = assessment.risk_score
    level = assessment.risk_level
    narrative_verdict = assessment.verdict
    summary = _build_narrative_summary(risk_score=risk_score, signal=hoax_signal)

    model_signal = _model_signal(text, title)
    weight = indobert.risk_weight() if model_signal is not None else 0.0
    if model_signal is not None:
        signals.append(model_signal)
        limitations.append(MODEL_LIMITATION)
        if weight > 0:
            risk_score = _blend_risk_score(
                heuristic=assessment.risk_score, model=model_signal.score, weight=weight
            )
            level = risk_level(risk_score)
            narrative_verdict = _decide_narrative_verdict(risk_score)
            limitations.append(_blend_limitation(weight))
        summary = _build_narrative_summary(risk_score=risk_score, signal=hoax_signal)
        if weight > 0:
            summary += (
                f" Model IndoBERT lokal menilai konten ini {model_signal.score}/100 ke arah "
                f"hoax dan menimbang {weight:.0%} dari indeks pola narasi; sisanya dari sinyal "
                "heuristik. Model tetap bukan bukti maupun penentu status."
            )
        else:
            summary += (
                f" Model IndoBERT lokal menilai konten ini {model_signal.score}/100 ke arah "
                "hoax, tetapi tidak diikutkan dalam indeks pola narasi (bobot 0)."
            )

    return AnalysisOutcome(
        signals=signals,
        claims=claims,
        # Status sementara: keputusan akhir diisi EBDE setelah bukti terkumpul.
        verdict=VERDICT_BELUM_DAPAT_DINILAI,
        risk_score=risk_score,
        risk_level=level,
        confidence=assessment.confidence,
        summary=summary,
        limitations=limitations,
        model_used=indobert.MODEL_VERSION if model_signal is not None else None,
        narrative_verdict=narrative_verdict,
    )


def apply_decision(outcome: AnalysisOutcome, decision) -> AnalysisOutcome:
    """Terapkan keputusan EBDE tanpa menyentuh risk score narasi."""
    outcome.verdict = decision.verdict
    outcome.confidence = decision.confidence
    outcome.decision = decision
    outcome.summary = f"{decision.summary} {outcome.summary}".strip()

    prefix = [DECISION_LIMITATION]
    if decision.insufficient_reason:
        prefix.append(decision.insufficient_reason)
    outcome.limitations = prefix + [
        item for item in outcome.limitations if item not in prefix
    ]
    return outcome
