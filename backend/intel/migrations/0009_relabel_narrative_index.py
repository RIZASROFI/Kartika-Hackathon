"""Selaraskan teks tersimpan dengan istilah "indeks pola narasi".

Skor narasi tidak lagi disebut "skor risiko": angkanya tidak punya band
rendah/sedang/tinggi dan tidak dibandingkan dengan verdict. Analisis lama
menyimpan kalimat hasil generator versi sebelumnya, jadi teksnya diperbarui
di sini tanpa menyentuh angka, verdict, maupun bukti.
"""

import re

from django.db import migrations

LEVEL_PATTERN = r"(?:rendah|sedang|tinggi|kritis)"

NARRATIVE_SUMMARY_RE = re.compile(
    rf"Skor risiko (?P<score>\d+)/100 \({LEVEL_PATTERN}\) mengukur pola penyebaran dan "
    r"kelemahan atribusi, bukan kebenaran isi\."
)

SIGNAL_LEVEL_RE = re.compile(
    rf"(mencatat \d+/100) dengan tingkat {LEVEL_PATTERN}\."
)

PLAIN_REPLACEMENTS = (
    ("skor risiko narasi", "indeks pola narasi"),
    ("dari skor risiko", "dari indeks pola narasi"),
    ("dalam skor risiko", "dalam indeks pola narasi"),
    ("Skor risiko memadukan", "Indeks pola narasi memadukan"),
    ("Skor ikut menimbang risiko narasi", "Skor ikut menimbang indeks pola narasi"),
)


def _rewrite(text: str) -> str:
    text = NARRATIVE_SUMMARY_RE.sub(
        lambda match: (
            f"Indeks pola narasi {match.group('score')}/100 mengukur pola penyebaran dan "
            "kelemahan atribusi, bukan kebenaran isi maupun tingkat keamanan konten."
        ),
        text,
    )
    text = SIGNAL_LEVEL_RE.sub(r"\1.", text)
    for old, new in PLAIN_REPLACEMENTS:
        text = text.replace(old, new)
    return text


def _rewrite_list(values) -> list:
    if not isinstance(values, list):
        return values
    return [_rewrite(item) if isinstance(item, str) else item for item in values]


def forwards(apps, schema_editor):
    Analysis = apps.get_model("intel", "Analysis")
    AnalysisSignal = apps.get_model("intel", "AnalysisSignal")

    for analysis in Analysis.objects.all().iterator():
        summary = _rewrite(analysis.summary or "")
        limitations = _rewrite_list(analysis.limitations or [])
        if summary != (analysis.summary or "") or limitations != (analysis.limitations or []):
            Analysis.objects.filter(pk=analysis.pk).update(
                summary=summary, limitations=limitations
            )

    for signal in AnalysisSignal.objects.all().iterator():
        explanation = _rewrite(signal.explanation or "")
        details = _rewrite_list(signal.details or [])
        if explanation != (signal.explanation or "") or details != (signal.details or []):
            AnalysisSignal.objects.filter(pk=signal.pk).update(
                explanation=explanation, details=details
            )


class Migration(migrations.Migration):

    dependencies = [
        ("intel", "0008_analysis_decision"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
