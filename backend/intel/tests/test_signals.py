from __future__ import annotations

from unittest import TestCase

from intel.analysis.hoax import analyze_hoax
from intel.analysis.pipeline import run_analysis

HOAX_TEXT = (
    "BREAKING! Pemerintah akan memadamkan listrik nasional selama 3 hari. Kabarnya keputusan "
    "ini diambil diam-diam karena krisis energi yang tidak pernah diberitakan. Sebarkan pesan "
    "ini ke semua grup sebelum dihapus! Buruan forward ke sepuluh orang. Jangan sampai keluarga "
    "kita tidak siap."
)

NEUTRAL_TEXT = (
    "Berdasarkan keterangan resmi Badan Meteorologi, Klimatologi, dan Geofisika, hujan lebat "
    "diperkirakan terjadi di sebagian wilayah Jawa Barat. Menurut juru bicara BMKG, masyarakat "
    "diminta memantau kanal resmi. Data dari sistem pemantauan menunjukkan peningkatan kelembapan. "
    "Pemerintah daerah menyiapkan posko darurat bersama Badan Penanggulangan Bencana Daerah."
)


class SignalTests(TestCase):
    def test_hoax_detector_flags_unattributed_urgency(self) -> None:
        signal, claims = analyze_hoax(HOAX_TEXT)
        self.assertGreaterEqual(signal.score, 60)
        self.assertTrue(claims, "klaim kandidat harus diekstrak")
        self.assertIn(
            claims[0].verdict, {"terindikasi_menyesatkan", "perlu_verifikasi"}
        )

    def test_hoax_detector_recognises_attribution(self) -> None:
        signal, _ = analyze_hoax(NEUTRAL_TEXT)
        self.assertLess(signal.score, 25)

    def test_viral_hoax_narrative_is_not_labelled_as_fact(self) -> None:
        text = (
            "Air kelapa bisa menyembuhkan kanker stadium 4. Menurut penelitian, 100% "
            "pasien sembuh total. Sebarkan ke keluarga Anda sebelum dihapus!"
        )
        outcome = run_analysis(text=text, title=None)
        # Sinyal narasi tidak menetapkan verdict; verdict diisi EBDE dari bukti.
        self.assertEqual(outcome.verdict, "belum_dapat_dinilai")
        self.assertNotEqual(outcome.narrative_verdict, "risiko_rendah")
        self.assertGreaterEqual(outcome.risk_score, 30)

    def test_pipeline_rejects_too_short_text(self) -> None:
        with self.assertRaises(ValueError):
            run_analysis(text="terlalu pendek", title=None)

    def test_pipeline_produces_single_hoax_signal(self) -> None:
        outcome = run_analysis(text=HOAX_TEXT, title=None)
        self.assertEqual([signal.category for signal in outcome.signals], ["hoax"])
        self.assertEqual(outcome.risk_score, outcome.signals[0].score)
        self.assertEqual(outcome.verdict, "belum_dapat_dinilai")
        self.assertIn(
            outcome.narrative_verdict,
            {
                "terindikasi_menyesatkan",
                "perlu_verifikasi",
                "risiko_rendah",
            },
        )
        self.assertTrue(outcome.limitations)
