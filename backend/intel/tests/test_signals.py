from __future__ import annotations

from datetime import datetime
from unittest import TestCase

from intel.analysis.bot import analyze_bot_signals
from intel.analysis.coordination import CoordinationCandidate, analyze_coordination
from intel.analysis.hoax import analyze_hoax
from intel.analysis.pipeline import run_analysis
from intel.analysis.provocation import analyze_provocation

PROVOCATIVE_TEXT = (
    "Kita sudah muak dengan rezim yang mengkhianati rakyat. Ayo kita geruduk gedung "
    "pemerintahan malam ini, jangan diam! Mereka penindas dan antek asing. Gulingkan "
    "sekarang sebelum terlambat. Serukan ke semua orang, kerahkan massa sebanyak mungkin. "
    "Kita harus lawan sampai mereka tumbang. Sebarkan selebar mungkin."
)

HOAX_TEXT = (
    "BREAKING! Pemerintah akan memadamkan listrik nasional selama 3 hari. Kabarnya keputusan "
    "ini diambil diam-diam karena krisis energi yang tidak pernah diberitakan. Sebarkan pesan "
    "ini ke semua grup sebelum dihapus! Buruan forward ke sepuluh orang. Jangan sampai keluarga "
    "kita tidak siap."
)

AI_TEXT = (
    "Penting untuk dicatat bahwa perkembangan teknologi telah membawa perubahan signifikan. "
    "Pertama, otomatisasi meningkatkan efisiensi. Kedua, analisis data mempercepat keputusan. "
    "Ketiga, muncul tantangan tata kelola. Selain itu, adopsi memerlukan kesiapan sumber daya. "
    "Dengan demikian, organisasi perlu menyusun kerangka kebijakan — termasuk evaluasi risiko. "
    "Secara keseluruhan, pendekatan bertahap membantu mengurangi risiko. Sebagai kesimpulan, "
    "kolaborasi menjadi kunci. Saya harap ini membantu."
)

NEUTRAL_TEXT = (
    "Berdasarkan keterangan resmi Badan Meteorologi, Klimatologi, dan Geofisika, hujan lebat "
    "diperkirakan terjadi di sebagian wilayah Jawa Barat. Menurut juru bicara BMKG, masyarakat "
    "diminta memantau kanal resmi. Data dari sistem pemantauan menunjukkan peningkatan kelembapan. "
    "Pemerintah daerah menyiapkan posko darurat bersama Badan Penanggulangan Bencana Daerah."
)


class SignalTests(TestCase):
    def test_provocation_scores_high_on_incitement(self) -> None:
        signal = analyze_provocation(PROVOCATIVE_TEXT)
        self.assertGreaterEqual(signal.score, 60)
        self.assertIn(signal.level, {"tinggi", "kritis"})
        self.assertGreater(signal.confidence, 0.4)
        self.assertTrue(
            any(
                "kekerasan" in detail.lower() or "penggulingan" in detail.lower()
                for detail in signal.details
            )
        )

    def test_provocation_stays_low_on_official_report(self) -> None:
        signal = analyze_provocation(NEUTRAL_TEXT)
        self.assertLess(signal.score, 25)
        self.assertEqual(signal.level, "rendah")

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

    def test_bot_signal_detects_ai_template(self) -> None:
        signal = analyze_bot_signals(AI_TEXT)
        self.assertGreaterEqual(signal.score, 50)
        self.assertLessEqual(signal.confidence, 0.6)
        self.assertTrue(any("model bahasa" in detail for detail in signal.details))

    def test_long_neutral_document_is_not_flagged(self) -> None:
        signal = analyze_provocation(NEUTRAL_TEXT * 30)
        self.assertLess(signal.score, 25, signal.details)

    def test_coordination_matches_near_duplicates(self) -> None:
        reference = datetime(2026, 10, 20, 10, 0, 0)
        candidates = [
            CoordinationCandidate(
                analysis_id="a-1",
                title="Peringatan listrik padam",
                text=HOAX_TEXT,
                reference_time=datetime(2026, 10, 20, 8, 0, 0),
            )
        ]
        result = analyze_coordination(
            text=HOAX_TEXT,
            title="Breaking listrik padam",
            reference_time=reference,
            candidates=candidates,
            threshold=0.28,
            min_corpus=1,
        )
        self.assertTrue(result.matches)
        self.assertGreaterEqual(result.signal.score, 60)
        self.assertAlmostEqual(result.matches[0].hours_apart or 0, 2.0, places=1)

    def test_pipeline_rejects_too_short_text(self) -> None:
        with self.assertRaises(ValueError):
            run_analysis(
                text="terlalu pendek",
                title=None,
                reference_time=datetime(2026, 10, 20),
            )

    def test_pipeline_produces_four_signals(self) -> None:
        outcome = run_analysis(
            text=HOAX_TEXT, title=None, reference_time=datetime(2026, 10, 20)
        )
        self.assertEqual(
            {signal.category for signal in outcome.signals},
            {"hoax", "provocation", "coordination", "bot_ai"},
        )
        self.assertIn(
            outcome.verdict,
            {
                "terkoordinasi",
                "terindikasi_menyesatkan",
                "provokatif",
                "perlu_verifikasi",
                "risiko_rendah",
            },
        )
        self.assertTrue(outcome.limitations)
