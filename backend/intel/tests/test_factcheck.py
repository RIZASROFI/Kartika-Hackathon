from __future__ import annotations

from unittest import mock

from django.test import TestCase, override_settings

from intel.models import Analysis, FactCheckQuery
from intel.services.analysis_service import create_analysis
from intel.services.factcheck import (
    FactCheckError,
    apply_limitation,
    classify_rating,
    overlap_ratio,
    run_factcheck,
)

ARTICLE_TEXT = (
    "Bantuan sosial Rp 5 juta untuk semua warga bisa diambil lewat link pendaftaran "
    "berikut. Buruan daftar sebelum kuota habis! Cukup isi nama dan nomor rekening. "
    "Sebarkan link ini ke semua grup keluarga supaya tidak ada yang ketinggalan."
)

GOOGLE_PAYLOAD = {
    "claims": [
        {
            "text": "Bantuan sosial Rp 5 juta diambil lewat link pendaftaran",
            "claimant": "Grup WhatsApp",
            "claimDate": "2026-02-01T00:00:00Z",
            "claimReview": [
                {
                    "publisher": {"name": "Tempo.co", "site": "tempo.co"},
                    "url": "https://www.tempo.co/cekfakta/bansos-link",
                    "title": "[Fakta atau Hoaks] Bansos Rp 5 juta lewat link",
                    "reviewDate": "2026-03-12T00:00:00Z",
                    "textualRating": "Keliru",
                },
                {
                    "publisher": {"name": "AFP Cek Fakta", "site": "afp.com"},
                    "url": "https://factcheck.afp.com/bansos",
                    "title": "Klaim bansos lewat link tidak benar",
                    "reviewDate": "2026-03-10T00:00:00Z",
                    "textualRating": "Salah",
                },
            ],
        }
    ]
}

TEST_SETTINGS = dict(
    FACTCHECK_ENABLED=True,
    GOOGLE_FACTCHECK_API_KEY="test-key",
    FACTCHECK_MAX_QUERIES=2,
    FACTCHECK_MIN_OVERLAP=0.45,
)


class RatingClassificationTests(TestCase):
    def test_indonesian_ratings(self) -> None:
        self.assertEqual(classify_rating("Keliru"), "hoax")
        self.assertEqual(classify_rating("Hoaks"), "hoax")
        self.assertEqual(classify_rating("Tidak Benar"), "hoax")
        self.assertEqual(classify_rating("Sebagian Benar"), "sebagian_benar")
        self.assertEqual(classify_rating("Benar"), "fakta")
        self.assertEqual(classify_rating("Tidak dapat diverifikasi"), "tidak_jelas")
        self.assertEqual(classify_rating(None), "tidak_jelas")

    def test_overlap_filters_unrelated_claims(self) -> None:
        source = {"bantuan", "sosial", "link", "pendaftaran"}
        self.assertGreater(
            overlap_ratio("Bantuan sosial lewat link pendaftaran", source), 0.7
        )
        self.assertLess(overlap_ratio("Vaksin covid memakai microchip", source), 0.45)


@override_settings(**TEST_SETTINGS)
class FactCheckClientTests(TestCase):
    def test_matches_and_caches_google_results(self) -> None:
        with mock.patch(
            "intel.services.factcheck._fetch_claims", return_value=GOOGLE_PAYLOAD
        ) as fetch:
            result = run_factcheck(
                text=ARTICLE_TEXT,
                title="Bansos Rp 5 juta lewat link",
                claims=[],
            )
            self.assertEqual(result.status, "matched")
            self.assertEqual(len(result.hits), 2)
            self.assertEqual(result.hits[0].publisher, "Tempo.co")
            self.assertEqual(result.hits[0].status, "hoax")
            first_call_count = fetch.call_count
            self.assertGreaterEqual(FactCheckQuery.objects.count(), 1)

            cached = run_factcheck(
                text=ARTICLE_TEXT,
                title="Bansos Rp 5 juta lewat link",
                claims=[],
            )
            self.assertEqual(cached.status, "matched")
            self.assertEqual(fetch.call_count, first_call_count)

    def test_unreachable_api_degrades_gracefully(self) -> None:
        with mock.patch(
            "intel.services.factcheck._fetch_claims",
            side_effect=FactCheckError("Koneksi gagal."),
        ):
            result = run_factcheck(text=ARTICLE_TEXT, title="Konten lain tanpa cache")
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.hits, [])
        self.assertIn("Koneksi gagal", result.message or "")

    def test_irrelevant_hits_are_discarded(self) -> None:
        with mock.patch(
            "intel.services.factcheck._fetch_claims", return_value=GOOGLE_PAYLOAD
        ):
            result = run_factcheck(
                text="Prakiraan cuaca Jakarta besok cerah berawan sepanjang hari.",
                title="Prakiraan cuaca Jakarta besok",
            )
        self.assertEqual(result.status, "no_match")

    @override_settings(FACTCHECK_ENABLED=False)
    def test_disabled_returns_status(self) -> None:
        result = run_factcheck(text=ARTICLE_TEXT, title="Bansos")
        self.assertEqual(result.status, "disabled")


@override_settings(**TEST_SETTINGS)
class AnalysisIntegrationTests(TestCase):
    def test_analysis_stores_factcheck_panel_and_evidence(self) -> None:
        with mock.patch(
            "intel.services.factcheck._fetch_claims", return_value=GOOGLE_PAYLOAD
        ):
            analysis = create_analysis(text=ARTICLE_TEXT, title="Bansos lewat link")

        self.assertEqual(analysis.factcheck["status"], "matched")
        self.assertEqual(analysis.factcheck["provider"], "google")
        self.assertEqual(analysis.factcheck["hits"][0]["rating"], "Keliru")

        evidence = analysis.evidence.filter(kind="factcheck")
        self.assertEqual(evidence.count(), 2)
        snippets = " ".join(item.snippet or "" for item in evidence)
        self.assertIn("Keliru", snippets)
        self.assertIn("Salah", snippets)

        self.assertNotIn(
            "Tidak ada pencocokan otomatis ke basis data fakta eksternal",
            " ".join(analysis.limitations),
        )
        self.assertIn("pemeriksa fakta eksternal", " ".join(analysis.limitations))

    def test_analysis_survives_api_failure(self) -> None:
        with mock.patch(
            "intel.services.factcheck._fetch_claims",
            side_effect=FactCheckError("HTTP 429 kuota habis."),
        ):
            analysis = create_analysis(
                text=ARTICLE_TEXT + " Segera daftar sebelum ditutup.",
                title="Bansos kuota habis",
            )

        self.assertEqual(analysis.factcheck["status"], "unavailable")
        self.assertFalse(analysis.evidence.filter(kind="factcheck").exists())
        self.assertEqual(Analysis.objects.filter(pk=analysis.pk).count(), 1)

    def test_apply_limitation_replaces_external_check_note(self) -> None:
        limitations = [
            "Tidak ada pencocokan otomatis ke basis data fakta eksternal; "
            "status klaim bersifat indikatif.",
            "Catatan lain.",
        ]
        updated = apply_limitation(limitations, "no_match")
        self.assertEqual(len(updated), 2)
        self.assertIn("Tidak ditemukan catatan pemeriksaan fakta", updated[0])
        self.assertEqual(updated[1], "Catatan lain.")
