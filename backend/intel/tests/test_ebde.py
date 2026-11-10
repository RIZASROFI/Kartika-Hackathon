"""Pengujian Evidence-Based Decision Engine dan integrasinya ke analisis."""

from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

from django.test import TestCase, override_settings

from intel.analysis.ebde import (
    ALIGNMENT_DIFFERENT,
    CLAIM_MISMATCH_REASON,
    DECISION_ENGINE_VERSION,
    STANCE_NEUTRAL,
    STANCE_PARTIAL,
    STANCE_REFUTE,
    STANCE_SUPPORT,
    VERDICT_BELUM_DAPAT_DINILAI,
    VERDICT_PERLU_VERIFIKASI,
    VERDICT_TERINDIKASI_FAKTA,
    VERDICT_TERINDIKASI_HOAKS,
    EvidenceItem,
    assess_evidence,
    build_evidence_items,
    credibility_score,
    recency_score,
)
from intel.analysis.pipeline import ENGINE_VERSION, run_analysis
from intel.models import Analysis
from intel.serializers import AnalysisDetailSerializer
from intel.services import claim_match
from intel.services.analysis_service import analyze_text_local, create_analysis
from intel.services.claim_match import CLAIM_MATCH_LIMITATION
from intel.services.factcheck import FactCheckError
from intel.services.llm import LLMError


class DecisionScaleJsonTests(TestCase):
    """UI menulis bobot sebagai "nilai/maksimum"; skalanya harus ikut terkirim."""

    def test_decision_json_exposes_dimension_maxima(self):
        decision = assess_evidence(
            items=[make_item(url="https://contoh.com/1", publisher="contoh.com")]
        )
        payload = decision.to_json()
        assert payload["scales"] == {
            "relevance": 1.0,
            "credibility": 0.95,
            "recency": 1.0,
            "weight": 0.95,
        }
        assert payload["items"][0]["credibility"] <= payload["scales"]["credibility"]

ARTICLE = (
    "Bantuan sosial Rp 5 juta untuk semua warga bisa diambil lewat link berikut. "
    "Buruan daftar sebelum kuota habis! Cukup isi nama dan nomor rekening. "
    "Sebarkan link ini ke semua grup keluarga supaya tidak ada yang ketinggalan."
)

TEST_SETTINGS = dict(
    FACTCHECK_ENABLED=True,
    GOOGLE_FACTCHECK_API_KEY="test-key",
    MAFINDO_ENABLED=False,
    FACTCHECK_MIN_OVERLAP=0.45,
)


def make_item(
    *,
    url: str,
    publisher: str,
    stance: str = STANCE_REFUTE,
    relevance: float = 0.9,
    credibility: float = 0.9,
    recency: float = 1.0,
) -> EvidenceItem:
    return EvidenceItem(
        title="Cek fakta klaim",
        url=url,
        publisher=publisher,
        snippet="Isi pemeriksaan fakta.",
        stance=stance,
        kind="factcheck",
        provider="google",
        relevance=relevance,
        credibility=credibility,
        recency=recency,
        group=url.split("/")[2],
    )


def factcheck_hit(**overrides) -> SimpleNamespace:
    """Temuan cek fakta tiruan dengan bentuk yang sama seperti FactCheckHit."""
    base = dict(
        claim="[SALAH] Pengadilan Negeri Surakarta Menyatakan Ijazah Jokowi Palsu",
        rating="Salah",
        status="hoax",
        publisher="Mafindo",
        url="https://regional.kompas.com/read/2026/04/14/pn-solo",
        title="[SALAH] Pengadilan Negeri Surakarta Menyatakan Ijazah Jokowi Palsu",
        review_date="2026-09-29",
        query="pengadilan",
        provider="mafindo",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def payload_for(rating: str, *, second_rating: str | None = None) -> dict:
    reviews = [
        {
            "publisher": {"name": "Tempo.co"},
            "url": "https://www.tempo.co/cekfakta/bansos-link",
            "title": "Cek fakta bansos lewat link",
            "reviewDate": "2026-10-01T00:00:00Z",
            "textualRating": rating,
        },
        {
            "publisher": {"name": "MAFINDO"},
            "url": "https://turnbackhoax.id/bansos-lewat-link",
            "title": "Bantuan sosial lewat link pendaftaran",
            "reviewDate": "2026-09-20T00:00:00Z",
            "textualRating": second_rating or rating,
        },
    ]
    return {
        "claims": [
            {
                "text": "Bantuan sosial Rp 5 juta diambil lewat link pendaftaran",
                "claimReview": reviews,
            }
        ]
    }


class EvidenceScoringTests(TestCase):
    def test_publisher_credibility_tiers(self) -> None:
        self.assertGreater(
            credibility_score("MAFINDO", "https://turnbackhoax.id/a"),
            credibility_score("Detik", "https://detik.com/a"),
        )
        self.assertGreater(
            credibility_score("Detik", "https://detik.com/a"),
            credibility_score("Kanal pribadi", "https://youtube.com/watch?v=1"),
        )
        self.assertGreater(
            credibility_score(None, "https://umkm.go.id/berita"),
            credibility_score("Blog pribadi", "https://blog.example.org/a"),
        )
        self.assertEqual(credibility_score("Tanpa nama"), 0.5)

    def test_recency_decays_and_floors(self) -> None:
        recent = recency_score("2026-10-01T00:00:00Z")
        old = recency_score("2020-01-01T00:00:00Z")
        self.assertGreater(recent, old)
        self.assertEqual(old, 0.25)
        self.assertEqual(recency_score(None), 0.6)

    def test_build_items_maps_factcheck_and_claim_statuses(self) -> None:
        class Hit:
            title = "Cek fakta bansos lewat link"
            claim = "Bantuan sosial Rp 5 juta diambil lewat link pendaftaran"
            status = "hoax"
            rating = "Salah"
            url = "https://turnbackhoax.id/bansos"
            publisher = "MAFINDO"
            provider = "mafindo"
            review_date = "2026-10-01T00:00:00Z"

        class ClaimResult:
            claim = "Bantuan sosial Rp 5 juta diambil lewat link"
            status = "didukung"
            citations = [
                {
                    "title": "Penjelasan bansos resmi",
                    "url": "https://kominfo.go.id/bansos",
                    "publisher": "kominfo.go.id",
                    "snippet": "Bantuan sosial disalurkan lewat rekening penerima.",
                }
            ]

        class UnclearResult:
            claim = "Klaim tanpa bukti"
            status = "tidak_cukup_bukti"
            citations = []

        items = build_evidence_items(
            factcheck_hits=[Hit()],
            claim_results=[ClaimResult(), UnclearResult()],
            text=ARTICLE,
        )

        self.assertEqual(len(items), 2)
        stances = {item.url: item.stance for item in items}
        self.assertEqual(stances["https://turnbackhoax.id/bansos"], STANCE_REFUTE)
        self.assertEqual(stances["https://kominfo.go.id/bansos"], STANCE_SUPPORT)

    def test_claim_citation_published_date_drives_recency(self) -> None:
        """Tanggal terbit hasil pencarian harus dipakai, bukan nilai netral."""
        published = "2026-10-01T00:00:00Z"
        claim = SimpleNamespace(
            claim="Bantuan sosial Rp 5 juta diambil lewat link pendaftaran",
            status="didukung",
            citations=[
                {
                    "title": "Bantuan sosial Rp 5 juta diambil lewat link pendaftaran",
                    "url": "https://kominfo.go.id/bansos",
                    "publisher": "kominfo.go.id",
                    "snippet": "Bantuan sosial Rp 5 juta diambil lewat link pendaftaran.",
                    "published_date": published,
                },
                {
                    "title": "Bantuan sosial Rp 5 juta diambil lewat link pendaftaran",
                    "url": "https://tempo.co/bansos",
                    "publisher": "tempo.co",
                    "snippet": "Bantuan sosial Rp 5 juta diambil lewat link pendaftaran.",
                },
            ],
        )

        items = build_evidence_items(claim_results=[claim], text=ARTICLE)
        by_url = {item.url: item for item in items}

        dated = by_url["https://kominfo.go.id/bansos"]
        self.assertEqual(dated.published_at, published)
        self.assertAlmostEqual(
            dated.recency, recency_score(published), places=4
        )
        # Tanpa tanggal terbit, kebaruan tetap memakai nilai netral.
        undated = by_url["https://tempo.co/bansos"]
        self.assertIsNone(undated.published_at)
        self.assertAlmostEqual(undated.recency, 0.6, places=4)

    def test_partial_rating_becomes_partial_stance(self) -> None:
        class Hit:
            title = "Cek fakta bansos"
            claim = "Bantuan sosial Rp 5 juta lewat link"
            status = "sebagian_benar"
            rating = "Sebagian benar"
            url = "https://tempo.co/cek-fakta"
            publisher = "Tempo.co"
            provider = "google"
            review_date = "2026-10-01T00:00:00Z"

        items = build_evidence_items(factcheck_hits=[Hit()], text=ARTICLE)
        self.assertEqual(items[0].stance, STANCE_PARTIAL)

    def test_long_article_can_cover_a_short_claim(self) -> None:
        """Klaim pendek yang dibahas artikel panjang tidak boleh terhukum lantai 0,35."""
        text = "Kasus dugaan penyadapan ilegal oleh mantan Kapolri Listyo Sigit"
        claim = SimpleNamespace(
            claim=text,
            status="didukung",
            citations=[
                {
                    "title": "Mantan Kapolri Listyo Sigit ditetapkan tersangka penyadapan",
                    "url": "https://www.bbc.com/indonesia/articles/x",
                    "publisher": "bbc.com",
                    "snippet": (
                        "Mabes Polri menetapkan tersangka dalam kasus dugaan penyadapan "
                        "ilegal. Tiga perwira yang sebelumnya ditetapkan sebagai tersangka "
                        "adalah mantan Kapolri Jenderal Listyo Sigit, Kadivkum Polri, dan "
                        "seorang perwira lain. Penyidikan masih berlanjut."
                    ),
                },
                {
                    "title": "Kasus penyadapan, Polri periksa 13 saksi",
                    "url": "https://news.detik.com/berita/d-1/x",
                    "publisher": "news.detik.com",
                    "snippet": (
                        "Polri terus mendalami kasus penyadapan ilegal oleh mantan Kapolri "
                        "Listyo Sigit. Belasan saksi sudah diperiksa termasuk ahli ITE."
                    ),
                },
            ],
        )

        items = build_evidence_items(claim_results=[claim], text=text)
        self.assertTrue(all(item.relevance > 0.35 for item in items))
        decision = assess_evidence(items=items, narrative_risk=12)
        self.assertEqual(decision.verdict, VERDICT_TERINDIKASI_FAKTA)


class DecisionTests(TestCase):
    def test_supporting_evidence_yields_indicated_fact(self) -> None:
        decision = assess_evidence(
            items=[
                make_item(url="https://turnbackhoax.id/a", publisher="MAFINDO", stance=STANCE_SUPPORT),
                make_item(url="https://kominfo.go.id/b", publisher="Kominfo", stance=STANCE_SUPPORT),
            ]
        )
        self.assertEqual(decision.verdict, VERDICT_TERINDIKASI_FAKTA)
        self.assertTrue(decision.sufficient)
        self.assertEqual(decision.support_groups, 2)
        self.assertEqual(decision.refute_weight, 0.0)

    def test_refuting_evidence_yields_indicated_hoax(self) -> None:
        decision = assess_evidence(
            items=[
                make_item(url="https://turnbackhoax.id/a", publisher="MAFINDO"),
                make_item(url="https://tempo.co/b", publisher="Tempo.co"),
            ]
        )
        self.assertEqual(decision.verdict, VERDICT_TERINDIKASI_HOAKS)
        # Dua domain × (0,9 relevansi × 0,9 kredibilitas × 1,0 kebaruan) = 1,62.
        self.assertAlmostEqual(decision.refute_weight, 1.62, places=2)
        self.assertFalse(decision.conflict)

    def test_conflicting_evidence_needs_verification(self) -> None:
        decision = assess_evidence(
            items=[
                make_item(url="https://turnbackhoax.id/a", publisher="MAFINDO"),
                make_item(
                    url="https://kominfo.go.id/b",
                    publisher="Kominfo",
                    stance=STANCE_SUPPORT,
                ),
            ]
        )
        self.assertEqual(decision.verdict, VERDICT_PERLU_VERIFIKASI)
        self.assertTrue(decision.conflict)
        self.assertIn("bertentangan", decision.insufficient_reason or "")
        self.assertGreaterEqual(decision.support_weight, 0.3)
        self.assertGreaterEqual(decision.refute_weight, 0.3)

    def test_corroborated_uncontested_evidence_decides_below_weight_threshold(self) -> None:
        # Kasus nyata: tiga domain membantah dengan relevansi/kredibilitas moderat,
        # total bobot di bawah 0,60 tetapi tidak ada bukti pendukung sama sekali.
        decision = assess_evidence(
            items=[
                make_item(
                    url="https://turnbackhoax.id/a",
                    publisher="TurnBackHoax.ID",
                    relevance=0.45,
                    credibility=0.95,
                    recency=0.6,
                ),
                make_item(
                    url="https://umkm.go.id/b",
                    publisher="umkm.go.id",
                    relevance=0.35,
                    credibility=0.8,
                    recency=0.6,
                ),
                make_item(
                    url="https://tribratanews.polri.go.id/c",
                    publisher="tribratanews.polri.go.id",
                    relevance=0.35,
                    credibility=0.8,
                    recency=0.6,
                ),
            ]
        )
        self.assertLess(decision.refute_weight, 0.60)
        self.assertEqual(decision.verdict, VERDICT_TERINDIKASI_HOAKS)
        self.assertIn("tanpa bukti pendukung", decision.rationale)

    def test_single_weak_source_is_not_enough(self) -> None:
        decision = assess_evidence(
            items=[
                make_item(
                    url="https://blog.example.org/a",
                    publisher="Blog pribadi",
                    relevance=0.4,
                    credibility=0.3,
                    recency=0.5,
                )
            ]
        )
        self.assertEqual(decision.verdict, VERDICT_PERLU_VERIFIKASI)
        self.assertFalse(decision.sufficient)
        self.assertIn("domain independen", decision.insufficient_reason or "")

    def test_single_strong_factcheck_may_stand_alone(self) -> None:
        decision = assess_evidence(
            items=[
                make_item(
                    url="https://turnbackhoax.id/a",
                    publisher="MAFINDO",
                    relevance=0.95,
                    credibility=0.95,
                    recency=1.0,
                )
            ]
        )
        self.assertTrue(decision.sufficient)
        self.assertEqual(decision.verdict, VERDICT_TERINDIKASI_HOAKS)

    def test_single_credible_factcheck_below_weight_threshold_decides(self) -> None:
        """Pengecualian satu sumber kredibel harus dipakai oleh verdict, bukan
        hanya oleh flag `sufficient`."""
        decision = assess_evidence(
            items=[
                make_item(
                    url="https://tempo.co/cekfakta/mbg",
                    publisher="Tempo.co",
                    relevance=0.9,
                    credibility=0.95,
                    recency=0.6,
                )
            ]
        )
        self.assertLess(decision.refute_weight, 0.60)
        self.assertTrue(decision.sufficient)
        self.assertEqual(decision.verdict, VERDICT_TERINDIKASI_HOAKS)

    def test_single_credible_partial_factcheck_needs_verification(self) -> None:
        decision = assess_evidence(
            items=[
                make_item(
                    url="https://tempo.co/cekfakta/mbg",
                    publisher="Tempo.co",
                    stance=STANCE_PARTIAL,
                    relevance=0.6,
                    credibility=0.95,
                    recency=0.6,
                )
            ]
        )
        self.assertLess(decision.partial_weight, 0.50)
        self.assertTrue(decision.sufficient)
        self.assertEqual(decision.verdict, VERDICT_PERLU_VERIFIKASI)
        self.assertIn("sebagian benar", decision.insufficient_reason or "")

    def test_single_credible_source_cannot_decide_the_opposite_side(self) -> None:
        """Temuan kredibel yang membantah tidak boleh memenangkan sisi pendukung."""
        decision = assess_evidence(
            items=[
                make_item(
                    url="https://tempo.co/cekfakta/mbg",
                    publisher="Tempo.co",
                    relevance=0.9,
                    credibility=0.95,
                    recency=0.6,
                ),
                make_item(
                    url="https://blog.example.org/a",
                    publisher="Blog pribadi",
                    stance=STANCE_SUPPORT,
                    relevance=0.5,
                    credibility=0.3,
                    recency=0.6,
                ),
            ]
        )
        self.assertEqual(decision.verdict, VERDICT_TERINDIKASI_HOAKS)

    def test_no_evidence_never_forces_a_verdict(self) -> None:
        decision = assess_evidence(
            items=[],
            provider_status={"factcheck": "unavailable", "claim_check": "disabled"},
        )
        self.assertEqual(decision.verdict, VERDICT_BELUM_DAPAT_DINILAI)
        self.assertFalse(decision.sufficient)
        self.assertIn("tidak dapat dihubungi", decision.insufficient_reason or "")

    def test_inconclusive_retrieval_is_reported_as_found_but_unhelpful(self) -> None:
        """Sumber yang sudah diambil tetapi tidak menilai klaim bukan "tanpa bukti"."""
        decision = assess_evidence(
            items=[],
            provider_status={"factcheck": "no_match", "claim_check": "verified"},
        )
        self.assertEqual(decision.verdict, VERDICT_BELUM_DAPAT_DINILAI)
        reason = decision.insufficient_reason or ""
        self.assertIn("tidak ada yang secara eksplisit", reason)
        self.assertNotIn("Belum ada bukti eksternal", reason)

    def test_narrative_risk_is_not_evidence(self) -> None:
        decision = assess_evidence(items=[], narrative_risk=97)
        self.assertEqual(decision.verdict, VERDICT_BELUM_DAPAT_DINILAI)
        self.assertEqual(decision.support_weight, 0.0)
        self.assertEqual(decision.refute_weight, 0.0)
        self.assertEqual(decision.narrative_risk, 97)

    def test_factcheck_claim_mismatch_is_context_only(self) -> None:
        """Temuan untuk klaim lain tidak boleh menjadi sisi pembantah."""
        text = (
            "Joko Widodo hadir dan bersaksi di Pengadilan Negeri Jakarta Timur terkait "
            "kasus dugaan tudingan ijazah palsu dengan terdakwa Roy Suryo."
        )
        hit = factcheck_hit()
        items = build_evidence_items(
            factcheck_hits=[hit],
            text=text,
            factcheck_alignment={hit.url: ALIGNMENT_DIFFERENT},
        )
        self.assertEqual(items[0].stance, STANCE_NEUTRAL)
        self.assertIn("klaim yang berbeda", items[0].note)
        self.assertEqual(items[0].to_json()["note"], items[0].note)

        decision = assess_evidence(
            items=[
                *items,
                make_item(
                    url="https://www.antaranews.com/berita/1",
                    publisher="antaranews.com",
                    stance=STANCE_SUPPORT,
                ),
                make_item(
                    url="https://www.bbc.com/indonesia/articles/1",
                    publisher="bbc.com",
                    stance=STANCE_SUPPORT,
                ),
            ]
        )
        self.assertEqual(decision.verdict, VERDICT_TERINDIKASI_FAKTA)
        self.assertFalse(decision.conflict)
        self.assertEqual(decision.refute_weight, 0.0)
        self.assertEqual(decision.refute_groups, 0)

    def test_all_mismatched_evidence_yields_no_verdict(self) -> None:
        hit = factcheck_hit()
        decision = assess_evidence(
            items=build_evidence_items(
                factcheck_hits=[hit],
                text="Laporan sidang ijazah di Jakarta Timur.",
                factcheck_alignment={hit.url: ALIGNMENT_DIFFERENT},
            )
        )
        self.assertEqual(decision.verdict, VERDICT_BELUM_DAPAT_DINILAI)
        self.assertEqual(decision.insufficient_reason, CLAIM_MISMATCH_REASON)
        self.assertFalse(decision.sufficient)

    def test_verdict_is_independent_from_risk_score(self) -> None:
        decision = assess_evidence(
            items=[
                make_item(url="https://turnbackhoax.id/a", publisher="MAFINDO"),
                make_item(url="https://tempo.co/b", publisher="Tempo.co"),
            ],
            narrative_risk=3,
        )
        self.assertEqual(decision.verdict, VERDICT_TERINDIKASI_HOAKS)
        self.assertEqual(decision.narrative_risk, 3)

    def test_duplicate_url_is_counted_once(self) -> None:
        item = make_item(url="https://turnbackhoax.id/a", publisher="MAFINDO")
        duplicate = make_item(
            url="https://www.turnbackhoax.id/a/",
            publisher="TurnBackHoax",
            credibility=0.5,
        )
        decision = assess_evidence(
            items=[
                item,
                duplicate,
                make_item(url="https://tempo.co/b", publisher="Tempo.co"),
            ]
        )
        self.assertEqual(len(decision.items), 2)
        self.assertEqual(decision.refute_groups, 2)
        self.assertAlmostEqual(decision.refute_weight, 1.62, places=2)

    def test_same_publisher_is_one_independent_source(self) -> None:
        decision = assess_evidence(
            items=[
                make_item(
                    url="https://tempo.co/a", publisher="Tempo.co", credibility=0.85
                ),
                make_item(
                    url="https://tempo.co/b", publisher="Tempo.co", credibility=0.85
                ),
            ]
        )
        self.assertEqual(decision.refute_groups, 1)
        # Bobot domain = bobot artikel terkuat, bukan penjumlahan kedua artikel.
        self.assertAlmostEqual(decision.refute_weight, 0.765, places=2)
        # Dua artikel dari satu penerbit tetap satu sumber, dan artikel berita
        # tidak boleh menjadi dasar verdict tanpa pembanding independen.
        self.assertFalse(decision.sufficient)

    def test_partial_evidence_alone_needs_verification(self) -> None:
        decision = assess_evidence(
            items=[
                make_item(
                    url="https://tempo.co/a",
                    publisher="Tempo.co",
                    stance=STANCE_PARTIAL,
                ),
                make_item(
                    url="https://turnbackhoax.id/b",
                    publisher="MAFINDO",
                    stance=STANCE_PARTIAL,
                ),
            ]
        )
        self.assertEqual(decision.verdict, VERDICT_PERLU_VERIFIKASI)
        self.assertIn("sebagian benar", decision.insufficient_reason or "")
        self.assertGreaterEqual(decision.partial_weight, 0.5)


class PipelineSeparationTests(TestCase):
    def test_pipeline_returns_provisional_verdict_and_narrative_score(self) -> None:
        text = (
            "BREAKING! Pemerintah akan memadamkan listrik nasional selama 3 hari. "
            "Kabarnya keputusan ini diambil diam-diam karena krisis energi. "
            "Sebarkan pesan ini ke semua grup sebelum dihapus!"
        )
        outcome = run_analysis(text=text, title=None)
        self.assertEqual(outcome.verdict, VERDICT_BELUM_DAPAT_DINILAI)
        self.assertEqual(outcome.narrative_verdict, "terindikasi_menyesatkan")
        self.assertGreaterEqual(outcome.risk_score, 55)
        self.assertIn("bukan kebenaran isi", outcome.summary)


@override_settings(
    CLAIM_MATCH_ENABLED=True,
    LLM_ENABLED=True,
    LLM_API_KEY="test-key",
    LLM_MODEL="test-model",
)
class ClaimMatchTests(TestCase):
    def test_alignment_map_is_keyed_by_hit_url(self) -> None:
        hit = factcheck_hit()
        with mock.patch.object(
            claim_match,
            "call_json",
            return_value={
                "matches": [{"index": 1, "alignment": "berbeda", "reason": "klaim lain"}]
            },
        ) as call:
            alignment, status = claim_match.align_factcheck_hits(
                text="Jokowi bersaksi di PN Jakarta Timur.",
                title=None,
                claims=[],
                hits=[hit],
            )

        self.assertEqual(status, "applied")
        self.assertEqual(alignment, {hit.url: "berbeda"})
        self.assertIn("KLAIM PEMERIKSA FAKTA", call.call_args.kwargs["user"])

    def test_unknown_alignment_value_is_rejected(self) -> None:
        with mock.patch.object(
            claim_match,
            "call_json",
            return_value={"matches": [{"index": 1, "alignment": "benar"}]},
        ):
            alignment, status = claim_match.align_factcheck_hits(
                text="Teks konten.", title=None, claims=[], hits=[factcheck_hit()]
            )
        self.assertEqual((alignment, status), ({}, "failed"))

    def test_model_failure_is_returned_not_raised(self) -> None:
        with mock.patch.object(
            claim_match, "call_json", side_effect=LLMError("Kuota habis.")
        ):
            alignment, status = claim_match.align_factcheck_hits(
                text="Teks konten.", title=None, claims=[], hits=[factcheck_hit()]
            )
        self.assertEqual((alignment, status), ({}, "failed"))

    @override_settings(CLAIM_MATCH_ENABLED=False)
    def test_disabled_setting_skips_matching(self) -> None:
        alignment, status = claim_match.align_factcheck_hits(
            text="Teks konten.", title=None, claims=[], hits=[factcheck_hit()]
        )
        self.assertEqual((alignment, status), ({}, "disabled"))

    @override_settings(LLM_ENABLED=False)
    def test_disabled_model_skips_matching(self) -> None:
        alignment, status = claim_match.align_factcheck_hits(
            text="Teks konten.", title=None, claims=[], hits=[factcheck_hit()]
        )
        self.assertEqual((alignment, status), ({}, "disabled"))


@override_settings(**TEST_SETTINGS)
class DecisionPersistenceTests(TestCase):
    def test_analysis_stores_ebde_decision_and_evidence_weights(self) -> None:
        with mock.patch(
            "intel.services.factcheck._fetch_claims", return_value=payload_for("Salah")
        ):
            analysis = create_analysis(text=ARTICLE, title="Bansos lewat link")

        self.assertEqual(analysis.verdict, VERDICT_TERINDIKASI_HOAKS)
        self.assertEqual(analysis.engine_version, ENGINE_VERSION)
        self.assertEqual(analysis.decision["engine"], DECISION_ENGINE_VERSION)
        self.assertEqual(analysis.decision["verdict"], analysis.verdict)
        self.assertEqual(analysis.decision["refute_groups"], 2)
        self.assertTrue(analysis.decision["sufficient"])
        self.assertGreater(analysis.decision["refute_weight"], 1.0)

        first_item = analysis.decision["items"][0]
        for field in ("relevance", "credibility", "recency", "weight", "group"):
            self.assertIn(field, first_item)

        # Risk score narasi tetap tersimpan terpisah dari verdict.
        self.assertGreater(analysis.risk_score, 0)
        self.assertEqual(analysis.decision["narrative_risk"], analysis.risk_score)

    def test_supporting_factcheck_yields_indicated_fact(self) -> None:
        with mock.patch(
            "intel.services.factcheck._fetch_claims",
            return_value=payload_for("Benar"),
        ):
            analysis = create_analysis(text=ARTICLE, title="Bansos lewat link")
        self.assertEqual(analysis.verdict, VERDICT_TERINDIKASI_FAKTA)

    def test_mixed_ratings_need_verification(self) -> None:
        with mock.patch(
            "intel.services.factcheck._fetch_claims",
            return_value=payload_for("Salah", second_rating="Benar"),
        ):
            analysis = create_analysis(text=ARTICLE, title="Bansos lewat link")
        self.assertEqual(analysis.verdict, VERDICT_PERLU_VERIFIKASI)
        self.assertTrue(analysis.decision["conflict"])
        self.assertIn("bertentangan", analysis.decision["insufficient_reason"] or "")

    def test_mismatched_factcheck_hits_do_not_force_mixed_verdict(self) -> None:
        alignment = {
            "https://www.tempo.co/cekfakta/bansos-link": "berbeda",
            "https://turnbackhoax.id/bansos-lewat-link": "berbeda",
        }
        with (
            mock.patch(
                "intel.services.factcheck._fetch_claims",
                return_value=payload_for("Salah"),
            ),
            mock.patch(
                "intel.services.analysis_service.align_factcheck_hits",
                return_value=(alignment, "applied"),
            ),
        ):
            analysis = create_analysis(text=ARTICLE, title="Bansos lewat link")

        self.assertEqual(analysis.verdict, VERDICT_BELUM_DAPAT_DINILAI)
        self.assertEqual(analysis.decision["provider_status"]["claim_match"], "applied")
        self.assertIn(CLAIM_MATCH_LIMITATION, analysis.limitations)
        self.assertTrue(all(
            item["stance"] == STANCE_NEUTRAL for item in analysis.decision["items"]
        ))

    def test_api_failure_does_not_force_a_verdict(self) -> None:
        with mock.patch(
            "intel.services.factcheck._fetch_claims",
            side_effect=FactCheckError("Koneksi gagal."),
        ):
            analysis = create_analysis(text=ARTICLE, title="Bansos putus jaringan")

        self.assertEqual(analysis.verdict, VERDICT_BELUM_DAPAT_DINILAI)
        self.assertEqual(analysis.decision["provider_status"]["factcheck"], "unavailable")
        self.assertIn("tidak dapat dihubungi", analysis.decision["insufficient_reason"])
        self.assertGreater(analysis.risk_score, 0)

    def test_offline_local_analysis_is_not_forced_to_a_verdict(self) -> None:
        from django.utils import timezone

        analysis = analyze_text_local(
            text=ARTICLE, title=None, publisher=None, published_at=timezone.now()
        )
        self.assertEqual(analysis.verdict, VERDICT_BELUM_DAPAT_DINILAI)
        self.assertEqual(analysis.decision["item_count"], 0)
        self.assertIn("Belum Dapat Dinilai", analysis.summary)

    def test_serializer_exposes_decision_trace(self) -> None:
        with mock.patch(
            "intel.services.factcheck._fetch_claims", return_value=payload_for("Salah")
        ):
            analysis = create_analysis(text=ARTICLE, title="Bansos lewat link")

        payload = AnalysisDetailSerializer(analysis).data
        self.assertEqual(payload["decision"]["verdict"], VERDICT_TERINDIKASI_HOAKS)
        self.assertTrue(payload["decision"]["sufficient"])
        self.assertEqual(len(payload["decision"]["items"]), 2)
        self.assertEqual(payload["risk_score"], analysis.risk_score)

    def test_analysis_model_persists_decision_column(self) -> None:
        with mock.patch(
            "intel.services.factcheck._fetch_claims", return_value=payload_for("Salah")
        ):
            analysis = create_analysis(text=ARTICLE, title="Bansos lewat link")
        stored = Analysis.objects.get(pk=analysis.pk)
        self.assertEqual(stored.decision["verdict"], VERDICT_TERINDIKASI_HOAKS)
