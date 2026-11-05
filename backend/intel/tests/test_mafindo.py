from __future__ import annotations

from unittest import mock

from django.test import TestCase, override_settings

from intel.models import FactCheckQuery
from intel.services.analysis_service import create_analysis
from intel.services.factcheck import (
    FactCheckError,
    _extract_mafindo_hits,
    _fetch_mafindo,
    _mafindo_keywords,
    _tokens,
    run_factcheck,
)

ARTICLE_TEXT = (
    "Bantuan sosial Rp 5 juta untuk semua warga bisa diambil lewat link pendaftaran "
    "berikut. Buruan daftar sebelum kuota habis! Cukup isi nama dan nomor rekening. "
    "Sebarkan link ini ke semua grup keluarga supaya tidak ada yang ketinggalan."
)
ARTICLE_TITLE = "Bansos Rp 5 juta lewat link"

MAFINDO_ITEM = {
    "id": "37334",
    "authors": "Liputan 6",
    "status": "Salah",
    "classification": "CekFakta",
    "title": "Cek Fakta: Hoaks Link Pendaftaran Bansos Rp 5 Juta",
    "content": "Klaim link pendaftaran bantuan sosial Rp 5 juta beredar di Facebook.",
    "references": "https://kemensos.go.id/waspada-hoaks-terkait-bantuan-sosial",
    "tanggal": "2026-10-30",
    "claim_review": [
        {
            "claim_url": "https://www.liputan6.com/cek-fakta/read/8324345/cek-fakta-hoaks-bansos",
            "claim_rating_value": "1",
        }
    ],
}

MAFINDO_ONLY = dict(
    FACTCHECK_ENABLED=False,
    MAFINDO_ENABLED=True,
    MAFINDO_API_KEY="test-key",
    MAFINDO_MAX_QUERIES=2,
)

BOTH_PROVIDERS = dict(
    FACTCHECK_ENABLED=True,
    GOOGLE_FACTCHECK_API_KEY="test-google-key",
    MAFINDO_ENABLED=True,
    MAFINDO_API_KEY="test-mafindo-key",
    FACTCHECK_MIN_OVERLAP=0.45,
)

GOOGLE_PAYLOAD = {
    "claims": [
        {
            "text": "Bantuan sosial Rp 5 juta diambil lewat link pendaftaran",
            "claimReview": [
                {
                    "publisher": {"name": "Tempo.co"},
                    "url": "https://www.tempo.co/cekfakta/bansos-link",
                    "title": "[Fakta atau Hoaks] Bansos Rp 5 juta lewat link",
                    "reviewDate": "2026-03-12T00:00:00Z",
                    "textualRating": "Keliru",
                }
            ],
        }
    ]
}


class _FakeResponse:
    def __init__(self, status_code: int = 200, payload: object = None) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> object:
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class _FakeClient:
    """Klien httpx minimal agar pemanggilan HTTP dapat diperiksa tanpa jaringan."""

    last_call: dict = {}

    def __init__(self, response: _FakeResponse) -> None:
        self._response = response

    def __enter__(self) -> "_FakeClient":
        return self

    def __exit__(self, *exc_info: object) -> bool:
        return False

    def post(self, url: str, data: dict | None = None) -> _FakeResponse:
        _FakeClient.last_call = {"url": url, "data": data or {}}
        return self._response


class KeywordsTests(TestCase):
    def test_keywords_are_single_words_because_search_is_phrase_based(self) -> None:
        keywords = _mafindo_keywords(
            "Bantuan sosial Rp 5 juta yang diambil lewat link pendaftaran"
        )
        self.assertTrue(keywords)
        for keyword in keywords:
            self.assertNotIn(" ", keyword)

    def test_stopwords_and_numbers_are_not_used_as_queries(self) -> None:
        keywords = _mafindo_keywords(
            "Bantuan sosial Rp 5 juta yang diambil lewat link pendaftaran"
        )
        self.assertIn("pendaftaran", keywords)
        self.assertNotIn("yang", keywords)
        self.assertNotIn("5", keywords)

    def test_proper_nouns_are_preferred(self) -> None:
        keywords = _mafindo_keywords(
            "Gas Natuna akhirnya diekspor ke Singapura hari ini"
        )
        self.assertIn("natuna", keywords)
        self.assertIn("singapura", keywords)

    def test_role_words_are_skipped(self) -> None:
        keywords = _mafindo_keywords("Presiden Prabowo bertemu Menteri Bahlil")
        self.assertNotIn("presiden", keywords)
        self.assertNotIn("menteri", keywords)
        self.assertIn("prabowo", keywords)

    def test_single_token_is_returned_for_phrase_search(self) -> None:
        self.assertEqual(_mafindo_keywords("bansos"), ["bansos"])

    def test_limit_is_respected(self) -> None:
        keywords = _mafindo_keywords(
            "Natuna Singapura Prabowo Bahlil Lahadalia kedaulatan energi ekspor",
            limit=2,
        )
        self.assertEqual(len(keywords), 2)


class ExtractionTests(TestCase):
    def test_item_is_mapped_to_hit(self) -> None:
        hits = _extract_mafindo_hits(
            [MAFINDO_ITEM],
            query=ARTICLE_TITLE,
            source_tokens=_tokens(f"{ARTICLE_TITLE} {ARTICLE_TEXT}"),
        )
        self.assertEqual(len(hits), 1)
        hit = hits[0]
        self.assertEqual(hit.provider, "mafindo")
        self.assertEqual(hit.status, "hoax")
        self.assertEqual(hit.rating, "Salah")
        self.assertEqual(hit.publisher, "Liputan 6")
        self.assertEqual(hit.review_date, "2026-10-30")
        # Artikel cek fakta diambil dari claim_review, bukan dari referensi sumber.
        self.assertEqual(
            hit.url,
            "https://www.liputan6.com/cek-fakta/read/8324345/cek-fakta-hoaks-bansos",
        )
        self.assertFalse(hit.reference_only)

    def test_references_used_when_claim_review_is_empty(self) -> None:
        fake = {**MAFINDO_ITEM, "claim_review": []}
        hits = _extract_mafindo_hits(
            [fake],
            query=ARTICLE_TITLE,
            source_tokens=_tokens(f"{ARTICLE_TITLE} {ARTICLE_TEXT}"),
        )
        self.assertEqual(
            hits[0].url,
            "https://kemensos.go.id/waspada-hoaks-terkait-bantuan-sosial",
        )
        # Rujukan sumber bukan artikel pemeriksaan, jadi UI tidak menyebutnya demikian.
        self.assertTrue(hits[0].reference_only)

    def test_numeric_status_follows_documented_values(self) -> None:
        fake = {**MAFINDO_ITEM, "status": "2"}
        hits = _extract_mafindo_hits(
            [fake],
            query=ARTICLE_TITLE,
            source_tokens=_tokens(f"{ARTICLE_TITLE} {ARTICLE_TEXT}"),
        )
        self.assertEqual(hits[0].status, "hoax")

        fake = {**MAFINDO_ITEM, "status": "1", "title": "Cek Fakta: Bansos Rp 5 juta cair"}
        hits = _extract_mafindo_hits(
            [fake],
            query=ARTICLE_TITLE,
            source_tokens=_tokens(f"{ARTICLE_TITLE} {ARTICLE_TEXT}"),
        )
        self.assertEqual(hits[0].status, "fakta")

    def test_different_number_is_discarded(self) -> None:
        fake = {**MAFINDO_ITEM, "title": "Cek Fakta: Bansos Rp 10 juta lewat link"}
        hits = _extract_mafindo_hits(
            [fake],
            query=ARTICLE_TITLE,
            source_tokens=_tokens(f"{ARTICLE_TITLE} {ARTICLE_TEXT}"),
        )
        self.assertEqual(hits, [])

    def test_unrelated_title_is_discarded(self) -> None:
        fake = {**MAFINDO_ITEM, "title": "Cek Fakta: Vaksin bermagnet"}
        hits = _extract_mafindo_hits(
            [fake],
            query=ARTICLE_TITLE,
            source_tokens=_tokens(f"{ARTICLE_TITLE} {ARTICLE_TEXT}"),
        )
        self.assertEqual(hits, [])

    def test_named_entities_alone_are_not_enough(self) -> None:
        # Caption menyebut Prabowo dan Bahlil; artikel tentang pemecatan Bahlil
        # adalah klaim lain, jadi tidak boleh tampil sebagai bukti.
        caption = (
            "Berkat ketegasan Presiden Prabowo dan Menteri Bahlil Lahadalia, gas "
            "Natuna akhirnya pulang ke Indonesia dan tidak lagi diekspor."
        )
        fake = {
            **MAFINDO_ITEM,
            "title": "[SALAH] Prabowo Pecat Menteri ESDM Bahlil Lahadalia",
            "status": "Salah",
            "references": "https://turnbackhoax.id/prabowo-pecat-bahlil",
            "source_link": "https://www.youtube.com/watch?v=abc",
            "claim_review": [],
        }
        hits = _extract_mafindo_hits(
            [fake],
            query="lahadalia",
            match_text=caption,
            source_tokens=_tokens(caption),
        )
        self.assertEqual(hits, [])

    def test_claim_source_url_is_not_used_as_article_link(self) -> None:
        fake = {
            **MAFINDO_ITEM,
            "references": "https://turnbackhoax.id/bansos-lewat-link",
            "source_link": "https://www.youtube.com/watch?v=abc",
            "claim_review": [{"claim_url": "https://www.youtube.com/watch?v=abc"}],
        }
        hits = _extract_mafindo_hits(
            [fake],
            query=ARTICLE_TITLE,
            source_tokens=_tokens(f"{ARTICLE_TITLE} {ARTICLE_TEXT}"),
        )
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].url, "https://turnbackhoax.id/bansos-lewat-link")


class ClientTests(TestCase):
    def test_access_failed_body_is_treated_as_auth_error(self) -> None:
        client = _FakeClient(_FakeResponse(200, "Access failed"))
        with mock.patch("intel.services.factcheck.httpx.Client", return_value=client):
            with self.assertRaises(FactCheckError) as ctx:
                _fetch_mafindo(method="title", value="bansos")
        self.assertIn("Access failed", ctx.exception.message)

    def test_key_is_sent_in_form_body_without_trailing_slash(self) -> None:
        client = _FakeClient(_FakeResponse(200, [MAFINDO_ITEM]))
        with override_settings(
            MAFINDO_API_KEY="kunci-uji", MAFINDO_PAGE_SIZE=5
        ), mock.patch("intel.services.factcheck.httpx.Client", return_value=client):
            _fetch_mafindo(method="title", value="bansos")

        self.assertEqual(
            _FakeClient.last_call["url"],
            "https://yudistira.turnbackhoax.id/api/antihoax/search",
        )
        data = _FakeClient.last_call["data"]
        self.assertEqual(data["key"], "kunci-uji")
        self.assertEqual(data["method"], "title")
        self.assertEqual(data["value"], "bansos")

    def test_unexpected_payload_is_an_error(self) -> None:
        client = _FakeClient(_FakeResponse(200, {"message": "unexpected"}))
        with mock.patch("intel.services.factcheck.httpx.Client", return_value=client):
            with self.assertRaises(FactCheckError):
                _fetch_mafindo(method="title", value="bansos")

    def test_http_error_is_reported(self) -> None:
        client = _FakeClient(_FakeResponse(403, None))
        with mock.patch("intel.services.factcheck.httpx.Client", return_value=client):
            with self.assertRaises(FactCheckError) as ctx:
                _fetch_mafindo(method="title", value="bansos")
        self.assertEqual(ctx.exception.status_code, 403)


@override_settings(**MAFINDO_ONLY)
class MafindoRunTests(TestCase):
    def test_results_are_matched_and_cached(self) -> None:
        with mock.patch(
            "intel.services.factcheck._fetch_mafindo", return_value=[MAFINDO_ITEM]
        ) as fetch:
            result = run_factcheck(text=ARTICLE_TEXT, title=ARTICLE_TITLE)
            self.assertEqual(result.status, "matched")
            self.assertEqual(result.providers, ["mafindo"])
            self.assertEqual(result.hits[0].provider, "mafindo")
            self.assertEqual(result.hits[0].status, "hoax")
            self.assertTrue(result.keywords)
            for call in fetch.call_args_list:
                # Pencarian MAFINDO berbasis frasa: setiap kueri harus satu kata.
                self.assertNotIn(" ", call.kwargs["value"])
            calls = fetch.call_count
            self.assertGreaterEqual(calls, 1)
            self.assertGreaterEqual(FactCheckQuery.objects.count(), 1)

            cached = run_factcheck(text=ARTICLE_TEXT, title=ARTICLE_TITLE)
            self.assertEqual(cached.status, "matched")
            self.assertEqual(fetch.call_count, calls)

    def test_unreachable_api_degrades_gracefully(self) -> None:
        with mock.patch(
            "intel.services.factcheck._fetch_mafindo",
            side_effect=FactCheckError("Koneksi ke MAFINDO gagal."),
        ):
            result = run_factcheck(text=ARTICLE_TEXT, title=ARTICLE_TITLE)
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.providers, ["mafindo"])
        self.assertIn("MAFINDO", result.message or "")


@override_settings(**BOTH_PROVIDERS)
class CombinedProviderTests(TestCase):
    def test_hits_from_both_providers_are_merged(self) -> None:
        with mock.patch(
            "intel.services.factcheck._fetch_claims", return_value=GOOGLE_PAYLOAD
        ), mock.patch(
            "intel.services.factcheck._fetch_mafindo", return_value=[MAFINDO_ITEM]
        ):
            result = run_factcheck(text=ARTICLE_TEXT, title=ARTICLE_TITLE)

        self.assertEqual(result.status, "matched")
        self.assertEqual(result.providers, ["google", "mafindo"])
        self.assertEqual(
            {hit.provider for hit in result.hits}, {"google", "mafindo"}
        )

    def test_one_provider_failing_keeps_the_other_results(self) -> None:
        with mock.patch(
            "intel.services.factcheck._fetch_claims", return_value=GOOGLE_PAYLOAD
        ), mock.patch(
            "intel.services.factcheck._fetch_mafindo",
            side_effect=FactCheckError("Kuota MAFINDO habis (HTTP 429)."),
        ):
            result = run_factcheck(text=ARTICLE_TEXT, title=ARTICLE_TITLE)

        self.assertEqual(result.status, "matched")
        self.assertEqual({hit.provider for hit in result.hits}, {"google"})


@override_settings(**MAFINDO_ONLY)
class AnalysisIntegrationTests(TestCase):
    def test_mafindo_hits_become_evidence(self) -> None:
        with mock.patch(
            "intel.services.factcheck._fetch_mafindo", return_value=[MAFINDO_ITEM]
        ):
            analysis = create_analysis(text=ARTICLE_TEXT, title=ARTICLE_TITLE)

        self.assertEqual(analysis.factcheck["providers"], ["mafindo"])
        self.assertEqual(analysis.factcheck["status"], "matched")

        evidence = analysis.evidence.filter(kind="factcheck")
        self.assertEqual(evidence.count(), 1)
        self.assertEqual(evidence.first().publisher, "Liputan 6")
        self.assertIn("Salah", evidence.first().snippet or "")
