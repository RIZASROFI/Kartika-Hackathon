from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest import TestCase, mock

from django.test import TestCase as DjangoTestCase
from django.test import override_settings

from intel.analysis import indobert
from intel.analysis.pipeline import (
    ENGINE_VERSION,
    MODEL_LIMITATION,
    assess_signals,
    run_analysis,
)
from intel.analysis.text_stats import make_signal

from .test_signals import HOAX_TEXT

MODEL_SIGNAL = make_signal(
    category=indobert.CATEGORY,
    title=indobert.SIGNAL_TITLE,
    score=88,
    confidence=0.93,
    explanation="Model IndoBERT lokal menilai konten ini cenderung hoax.",
    details=["Label dominan Hoax — Hoax 92.0% · Fact 8.0%."],
)


class IndoBERTConfigTests(TestCase):
    def test_disabled_setting_skips_model(self) -> None:
        with override_settings(INDOBERT_ENABLED=False):
            self.assertFalse(indobert.is_available())
            self.assertIsNone(indobert.analyze_with_model(HOAX_TEXT, None))

    def test_missing_model_dir_is_unavailable(self) -> None:
        with override_settings(
            INDOBERT_ENABLED=True, INDOBERT_MODEL_DIR=Path("/tidak/ada/model")
        ):
            self.assertFalse(indobert.is_available())

    def test_labels_read_from_metadata_ignoring_description(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "label_mapping.json"
            path.write_text(
                json.dumps({"0": "Hoax", "1": "Fact", "description": {"Hoax": "x"}}),
                encoding="utf-8",
            )
            self.assertEqual(indobert._read_labels(Path(tmp)), {0: "Hoax", 1: "Fact"})

    def test_window_ids_caps_chunks_and_flags_truncation(self) -> None:
        windows, truncated, total = indobert._window_ids(list(range(2500)), 500, 2)
        self.assertEqual(len(windows), 2)
        self.assertEqual(total, 5)
        self.assertTrue(truncated)

        windows, truncated, total = indobert._window_ids(list(range(400)), 500, 2)
        self.assertEqual(len(windows), 1)
        self.assertEqual(total, 1)
        self.assertFalse(truncated)


class IndoBERTPipelineTests(TestCase):
    def test_model_signal_does_not_change_verdict(self) -> None:
        baseline = run_analysis(text=HOAX_TEXT, title=None)
        with mock.patch.object(indobert, "analyze_with_model", return_value=MODEL_SIGNAL):
            outcome = run_analysis(text=HOAX_TEXT, title=None)

        self.assertEqual(
            [signal.category for signal in outcome.signals], ["hoax", "indobert"]
        )
        self.assertEqual(outcome.risk_score, baseline.risk_score)
        self.assertEqual(outcome.verdict, baseline.verdict)
        self.assertEqual(
            outcome.narrative_verdict,
            assess_signals({"hoax": baseline.signals[0]}).verdict,
        )
        self.assertEqual(outcome.model_used, indobert.MODEL_VERSION)
        self.assertIn(MODEL_LIMITATION, outcome.limitations)
        self.assertIn("IndoBERT", outcome.summary)

    def test_model_failure_keeps_heuristic_analysis(self) -> None:
        with mock.patch.object(
            indobert, "analyze_with_model", side_effect=RuntimeError("bobot rusak")
        ):
            outcome = run_analysis(text=HOAX_TEXT, title=None)

        self.assertEqual([signal.category for signal in outcome.signals], ["hoax"])
        self.assertIsNone(outcome.model_used)
        self.assertNotIn(MODEL_LIMITATION, outcome.limitations)

    def test_model_signal_absent_when_model_disabled(self) -> None:
        with override_settings(INDOBERT_ENABLED=False):
            outcome = run_analysis(text=HOAX_TEXT, title=None)

        self.assertEqual([signal.category for signal in outcome.signals], ["hoax"])
        self.assertIsNone(outcome.model_used)


class IndoBERTPersistenceTests(DjangoTestCase):
    @mock.patch.object(indobert, "analyze_with_model", return_value=MODEL_SIGNAL)
    def test_signal_and_model_version_are_persisted(self, _mock) -> None:
        from django.utils import timezone

        from intel.services.analysis_service import analyze_text_local

        analysis = analyze_text_local(
            text=HOAX_TEXT, title=None, publisher=None, published_at=timezone.now()
        )

        self.assertEqual(analysis.model_used, indobert.MODEL_VERSION)
        self.assertEqual(analysis.engine_version, ENGINE_VERSION)
        self.assertEqual(
            sorted(analysis.signals.values_list("category", flat=True)),
            ["hoax", "indobert"],
        )
