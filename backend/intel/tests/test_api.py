from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APITestCase

from intel.models import Analysis, CoordinationLink
from intel.services.seed_service import seed_demo_data

SAMPLE_TEXT = (
    "Bantuan sosial Rp 5 juta untuk semua warga bisa diambil lewat link berikut. "
    "Buruan daftar sebelum kuota habis! Cukup isi nama dan nomor rekening. "
    "Sebarkan link ini ke semua grup keluarga supaya tidak ada yang ketinggalan. "
    "Program ini terbatas dan tidak diumumkan di televisi. "
    "Menurut sumber terpercaya, dana akan masuk dalam 24 jam."
)

NEAR_DUPLICATE_TEXT = (
    "Bantuan sosial Rp 5 juta untuk semua warga bisa diambil lewat link berikut. "
    "Buruan daftar sebelum kuota habis! Cukup isi nama dan nomor rekening. "
    "Sebarkan link ini ke semua grup keluarga supaya tidak ada yang ketinggalan. "
    "Program ini terbatas dan tidak diumumkan di televisi. "
    "Menurut sumber terpercaya, dana akan masuk dalam 24 jam. Segera forward."
)


class ApiTests(APITestCase):
    def test_health(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_create_analysis_from_text(self) -> None:
        response = self.client.post(
            "/api/v1/analyses",
            {
                "text": SAMPLE_TEXT,
                "title": "Bansos Rp 5 Juta",
                "publisher": "Demo",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        payload = response.json()
        self.assertIn(
            payload["verdict"],
            {
                "terkoordinasi",
                "terindikasi_menyesatkan",
                "provokatif",
                "perlu_verifikasi",
                "risiko_rendah",
            },
        )
        self.assertEqual(len(payload["signals"]), 4)
        self.assertTrue(payload["claims"])
        self.assertEqual(payload["evidence"][0]["kind"], "input_pengguna")
        self.assertEqual(payload["content"]["source_type"], "text")
        self.assertGreater(payload["risk_score"], 0)
        self.assertTrue(payload["created_at"].endswith("Z"))
        self.assertTrue(payload["limitations"])

    def test_validation_errors_are_flattened(self) -> None:
        response = self.client.post(
            "/api/v1/analyses", {"text": "terlalu pendek"}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIsInstance(response.json()["detail"], str)

    def test_missing_source_is_rejected(self) -> None:
        response = self.client.post("/api/v1/analyses", {}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("url", response.json()["detail"].lower())

    def test_ssrf_is_blocked(self) -> None:
        response = self.client.post(
            "/api/v1/analyses",
            {"url": "http://127.0.0.1:8000/secret"},
            format="json",
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn("tidak diizinkan", response.json()["detail"])

    def test_detail_not_found(self) -> None:
        response = self.client.get("/api/v1/analyses/tidak-ada")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Analisis tidak ditemukan.")

    def test_duplicate_analysis_creates_coordination_links(self) -> None:
        first = self.client.post(
            "/api/v1/analyses", {"text": SAMPLE_TEXT, "title": "Pesan A"}, format="json"
        )
        self.assertEqual(first.status_code, 201)
        second = self.client.post(
            "/api/v1/analyses",
            {"text": NEAR_DUPLICATE_TEXT, "title": "Pesan B"},
            format="json",
        )
        self.assertEqual(second.status_code, 201)
        payload = second.json()
        self.assertTrue(payload["related"], "konten mirip harus tertaut")
        self.assertGreater(payload["related"][0]["similarity"], 0.5)

        first_detail = self.client.get(f"/api/v1/analyses/{first.json()['id']}").json()
        self.assertTrue(
            first_detail["related"], "konten lama ikut diperbarui skor koordinasinya"
        )
        coordination = next(
            signal
            for signal in first_detail["signals"]
            if signal["category"] == "coordination"
        )
        self.assertGreaterEqual(coordination["score"], 50)
        self.assertEqual(CoordinationLink.objects.count(), 2)

    def test_list_filter_by_verdict(self) -> None:
        self.client.post(
            "/api/v1/analyses", {"text": SAMPLE_TEXT, "title": "Bansos"}, format="json"
        )
        verdict = Analysis.objects.first().verdict
        matching = self.client.get(f"/api/v1/analyses?verdict={verdict}&limit=10")
        self.assertEqual(matching.status_code, 200)
        self.assertEqual(len(matching.json()), 1)

        empty = self.client.get("/api/v1/analyses?verdict=tidak_ada")
        self.assertEqual(empty.status_code, 200)
        self.assertEqual(empty.json(), [])

    def test_dashboard_summary(self) -> None:
        self.client.post(
            "/api/v1/analyses", {"text": SAMPLE_TEXT, "title": "Bansos"}, format="json"
        )
        response = self.client.get("/api/v1/dashboard/summary")
        self.assertEqual(response.status_code, 200)
        summary = response.json()
        self.assertEqual(summary["totals"]["analyses"], 1)
        self.assertGreaterEqual(summary["totals"]["claims"], 1)
        self.assertEqual(len(summary["risk_trend"]), 14)
        self.assertEqual(len(summary["category_scores"]), 4)
        self.assertEqual(summary["recent_analyses"][0]["title"], "Bansos")

    def test_unknown_api_is_json_404(self) -> None:
        response = self.client.get("/api/v1/tidak-ada")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Not Found")

    def test_admin_requires_login_and_renders_for_superuser(self) -> None:
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])

        get_user_model().objects.create_superuser(
            username="admin", password="rahasia-demo-123", email="admin@example.org"
        )
        self.assertTrue(
            self.client.login(username="admin", password="rahasia-demo-123")
        )
        listing = self.client.get("/admin/intel/analysis/")
        self.assertEqual(listing.status_code, 200)


class SeedCommandTests(TestCase):
    def test_seed_demo_is_idempotent(self) -> None:
        call_command("seed_demo", verbosity=0)
        self.assertEqual(Analysis.objects.count(), 14)
        self.assertEqual(seed_demo_data(), 0)
        self.assertEqual(Analysis.objects.count(), 14)
