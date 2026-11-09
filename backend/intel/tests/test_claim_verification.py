"""Pengujian verifikasi klaim berbasis AI tanpa memanggil jaringan."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from intel.models import Analysis, Claim, Evidence
from intel.services.analysis_service import create_analysis
from intel.services.claim_verification import (
    STATUS_DIBANTAH,
    STATUS_DIDUKUNG,
    STATUS_TIDAK_CUKUP,
    run_claim_verification,
)
from intel.services.llm import LLMError, _extract_json, call_json
from intel.services.web_search import SearchError, WebEvidence, _parse_results

SAMPLE_TEXT = (
    "Bantuan sosial Rp 5 juta untuk semua warga bisa diambil lewat link berikut. "
    "Buruan daftar sebelum kuota habis! Cukup isi nama dan nomor rekening. "
    "Sebarkan link ini ke semua grup keluarga. Program ini terbatas dan tidak "
    "diumumkan di televisi. Menurut sumber terpercaya, dana akan masuk dalam 24 jam."
)

EVIDENCE = [
    WebEvidence(
        title="Cek fakta bansos Rp 5 juta",
        url="https://cekfakta.example.org/bansos",
        publisher="cekfakta.example.org",
        snippet="Pemerintah menegaskan informasi bansos Rp 5 juta lewat link adalah hoaks.",
        published_date="2026-10-01T00:00:00Z",
    ),
    WebEvidence(
        title="Penjelasan program bansos resmi",
        url="https://kominfo.example.go.id/bansos",
        publisher="kominfo.example.go.id",
        snippet="Penyaluran bansos dilakukan lewat rekening penerima, bukan link pendaftaran.",
    ),
]

AI_SETTINGS = dict(
    AI_CLAIM_CHECK_ENABLED=True,
    LLM_ENABLED=True,
    LLM_API_KEY="test-key",
    LLM_MODEL="test-model",
    EXA_API_KEY="test-key",
    CLAIM_CHECK_MAX_CLAIMS=2,
    CLAIM_CHECK_MAX_CITATIONS=3,
)


class ParsingTests(TestCase):
    def test_exa_payload_is_normalized(self) -> None:
        evidence = _parse_results(
            {
                "results": [
                    {
                        "title": "  Cek fakta   bansos ",
                        "url": "https://www.cekfakta.example.org/bansos",
                        "highlights": ["Bansos lewat link", "adalah hoaks"],
                    },
                    {
                        "url": "https://kominfo.example.go.id/bansos",
                        "text": "Penyaluran lewat rekening penerima.",
                    },
                    {"title": "Tanpa URL", "text": "diabaikan"},
                ]
            },
            claim="bansos",
        )

        self.assertEqual(len(evidence), 2)
        self.assertEqual(evidence[0].title, "Cek fakta bansos")
        self.assertEqual(evidence[0].publisher, "cekfakta.example.org")
        self.assertEqual(evidence[0].snippet, "Bansos lewat link adalah hoaks")
        self.assertEqual(evidence[1].publisher, "kominfo.example.go.id")
        self.assertEqual(evidence[1].snippet, "Penyaluran lewat rekening penerima.")

    def test_llm_json_survives_code_fence(self) -> None:
        payload = _extract_json('```json\n{"claims": [{"index": 1}]}\n```')
        self.assertEqual(payload["claims"][0]["index"], 1)


class LlmClientTests(TestCase):
    @override_settings(
        LLM_ENABLED=True,
        LLM_API_KEY="test-key",
        LLM_MODEL="test-model",
        LLM_BASE_URL="https://example.invalid/v1",
    )
    @patch("intel.services.llm.httpx.Client")
    def test_truncated_reply_has_clear_error(self, client_cls) -> None:
        response = MagicMock(status_code=200)
        response.json.return_value = {
            "choices": [
                {
                    "finish_reason": "length",
                    "message": {"content": '{"claims": ['},
                }
            ]
        }
        client_cls.return_value.__enter__.return_value.post.return_value = response

        with self.assertRaises(LLMError) as raised:
            call_json(system="sistem", user="pengguna")
        self.assertIn("terpotong", raised.exception.message)

    @override_settings(
        LLM_ENABLED=True,
        LLM_API_KEY="test-key",
        LLM_MODEL="test-model",
        LLM_BASE_URL="https://example.invalid/v1",
        LLM_MAX_TOKENS=300,
    )
    @patch("intel.services.llm.httpx.Client")
    def test_truncated_reply_is_retried_with_larger_budget(self, client_cls) -> None:
        truncated = MagicMock(status_code=200)
        truncated.json.return_value = {
            "choices": [{"finish_reason": "length", "message": {"content": '{"claims": ['}}]
        }
        complete = MagicMock(status_code=200)
        complete.json.return_value = {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "content": '{"claims": [{"index": 1, "status": "didukung"}]}'
                    },
                }
            ]
        }
        post = client_cls.return_value.__enter__.return_value.post
        post.side_effect = [truncated, complete]

        result = call_json(system="sistem", user="pengguna")

        self.assertEqual(result["claims"][0]["status"], "didukung")
        self.assertEqual(post.call_count, 2)
        budgets = [call.kwargs["json"]["max_tokens"] for call in post.call_args_list]
        self.assertEqual(budgets, [300, 600])


class ClaimVerificationDisabledTests(TestCase):
    @override_settings(AI_CLAIM_CHECK_ENABLED=True, LLM_ENABLED=False)
    def test_disabled_when_llm_not_configured(self) -> None:
        result = run_claim_verification(
            text=SAMPLE_TEXT, title="Bansos", claims=["Bantuan sosial Rp 5 juta dibagikan."]
        )
        self.assertEqual(result.status, "disabled")
        self.assertIn("LLM_ENABLED", result.message or "")


class ClaimVerificationValidationTests(TestCase):
    @override_settings(**AI_SETTINGS)
    @patch("intel.services.claim_verification.search_web", return_value=EVIDENCE)
    @patch("intel.services.claim_verification.call_json")
    def test_unretrieved_citations_are_rejected(self, call_json, _search) -> None:
        call_json.return_value = {
            "claims": [
                {
                    "index": 1,
                    "status": STATUS_DIDUKUNG,
                    "rationale": "Bukti menyebut program resmi.",
                    "citations": [
                        "https://cekfakta.example.org/bansos",
                        "https://karangan.example.net/tidak-ada",
                    ],
                },
                {
                    "index": 2,
                    "status": STATUS_DIBANTAH,
                    "rationale": "Tanpa sitasi.",
                    "citations": [],
                },
            ]
        }

        result = run_claim_verification(
            text=SAMPLE_TEXT,
            title="Bansos",
            claims=["Bansos Rp 5 juta lewat link.", "Dana masuk dalam 24 jam."],
        )

        self.assertEqual(result.status, "verified")
        self.assertEqual(len(result.claims), 2)
        self.assertEqual(result.claims[0].status, STATUS_DIDUKUNG)
        self.assertEqual(
            [citation["url"] for citation in result.claims[0].citations],
            ["https://cekfakta.example.org/bansos"],
        )
        # Tanggal terbit ikut diteruskan agar EBDE dapat menghitung kebaruan.
        self.assertEqual(
            result.claims[0].citations[0]["published_date"],
            "2026-10-01T00:00:00Z",
        )
        # Status tanpa sitasi valid diturunkan agar model tidak bisa mengarang dukungan.
        self.assertEqual(result.claims[1].status, STATUS_TIDAK_CUKUP)
        self.assertFalse(result.claims[1].citations)

    @override_settings(**AI_SETTINGS)
    @patch("intel.services.claim_verification.search_web", return_value=EVIDENCE)
    @patch("intel.services.claim_verification.call_json")
    def test_missing_claim_entry_is_marked_insufficient(self, call_json, _search) -> None:
        call_json.return_value = {"claims": []}
        result = run_claim_verification(
            text=SAMPLE_TEXT, title="Bansos", claims=["Klaim satu.", "Klaim dua."]
        )
        self.assertEqual(result.status, "verified")
        self.assertTrue(all(item.status == STATUS_TIDAK_CUKUP for item in result.claims))


class ClaimVerificationPersistenceTests(TestCase):
    @override_settings(**AI_SETTINGS)
    @patch("intel.services.claim_verification.search_web", return_value=EVIDENCE)
    @patch("intel.services.claim_verification.call_json")
    def test_analysis_persists_claim_status_and_cited_evidence(
        self, call_json, _search
    ) -> None:
        call_json.return_value = {
            "claims": [
                {
                    "index": 1,
                    "status": STATUS_DIDUKUNG,
                    "rationale": "Bukti pemeriksa fakta menguatkan klaim.",
                    "citations": ["https://cekfakta.example.org/bansos"],
                }
            ]
        }

        analysis = create_analysis(text=SAMPLE_TEXT, title="Bansos Rp 5 Juta")

        self.assertEqual(analysis.claim_check["status"], "verified")
        self.assertEqual(analysis.claim_check["model"], "test-model")
        self.assertGreaterEqual(analysis.claims.count(), 1)

        supported = analysis.claims.filter(evidence_status=STATUS_DIDUKUNG)
        self.assertEqual(supported.count(), 1)
        self.assertTrue(supported.first().citations)
        self.assertIsNotNone(supported.first().verified_at)

        web_evidence = Evidence.objects.filter(analysis=analysis, kind="pencarian_web")
        self.assertEqual(web_evidence.count(), 1)
        self.assertEqual(web_evidence.first().url, "https://cekfakta.example.org/bansos")
        self.assertTrue(
            any("model bahasa" in item for item in analysis.limitations),
            analysis.limitations,
        )

    @override_settings(**AI_SETTINGS)
    @patch(
        "intel.services.claim_verification.search_web",
        side_effect=SearchError("Kuota pencarian web habis (HTTP 429).", status_code=429),
    )
    def test_search_failure_keeps_analysis_complete(self, _search) -> None:
        analysis = create_analysis(text=SAMPLE_TEXT, title="Bansos")
        self.assertEqual(analysis.claim_check["status"], "unavailable")
        self.assertIn("429", analysis.claim_check["message"])
        self.assertGreaterEqual(Claim.objects.filter(analysis=analysis).count(), 1)
        self.assertFalse(analysis.claims.exclude(evidence_status="").exists())
        self.assertFalse(Evidence.objects.filter(analysis=analysis, kind="pencarian_web"))

    @override_settings(**AI_SETTINGS)
    @patch("intel.services.claim_verification.search_web", return_value=EVIDENCE)
    @patch("intel.services.claim_verification.call_json")
    def test_content_without_claim_still_searches_sources(
        self, call_json, search
    ) -> None:
        call_json.return_value = {
            "claims": [
                {
                    "index": 1,
                    "status": STATUS_DIDUKUNG,
                    "rationale": "Liputan media menguatkan pernyataan ini.",
                    "citations": ["https://cekfakta.example.org/bansos"],
                }
            ]
        }
        narrative = (
            "Pertemuan bilateral presiden dan menteri luar negeri membahas kerja "
            "sama ekonomi di kawasan."
        )

        analysis = create_analysis(text=narrative, title="Pertemuan Bilateral")

        search.assert_called()
        self.assertEqual(search.call_args.args[0], "Pertemuan Bilateral")
        self.assertEqual(analysis.claim_check["status"], "verified")
        self.assertEqual(analysis.claims.count(), 0)
        web_evidence = Evidence.objects.filter(analysis=analysis, kind="pencarian_web")
        self.assertEqual(web_evidence.count(), 1)
        self.assertEqual(web_evidence.first().url, "https://cekfakta.example.org/bansos")

    @override_settings(**AI_SETTINGS)
    @patch("intel.services.claim_verification.search_web", return_value=EVIDENCE)
    @patch("intel.services.claim_verification.call_json")
    def test_content_without_claim_uses_first_sentence_as_query(
        self, call_json, search
    ) -> None:
        call_json.return_value = {"claims": []}
        narrative = "Pertemuan bilateral presiden dan menteri luar negeri membahas kerja sama ekonomi."

        result = run_claim_verification(text=narrative, title=None, claims=[])

        self.assertEqual(search.call_args.args[0], narrative)
        self.assertEqual(result.status, "verified")

    @override_settings(**AI_SETTINGS)
    @patch("intel.services.claim_verification.search_web", return_value=EVIDENCE)
    @patch(
        "intel.services.claim_verification.call_json",
        side_effect=LLMError("Kuota model bahasa habis (HTTP 429).", status_code=429),
    )
    def test_llm_failure_keeps_analysis_complete(self, _call, _search) -> None:
        analysis = create_analysis(text=SAMPLE_TEXT, title="Bansos")
        self.assertEqual(analysis.claim_check["status"], "unavailable")
        self.assertEqual(Evidence.objects.filter(analysis=analysis, kind="pencarian_web").count(), 0)
        self.assertTrue(analysis.claims.exists())
