"""Pengisian data demo sintetis."""

from __future__ import annotations

import logging
from datetime import timedelta

from django.utils import timezone

from intel.demo_data import DEMO_ITEMS
from intel.models import Analysis
from intel.services.analysis_service import analyze_text_local

logger = logging.getLogger(__name__)


def seed_demo_data() -> int:
    """Isi database dengan analisis demo bila masih kosong."""
    if Analysis.objects.exists():
        return 0

    now = timezone.now()
    created = 0
    for item in sorted(DEMO_ITEMS, key=lambda entry: entry.hours_ago, reverse=True):
        published_at = now - timedelta(hours=item.hours_ago)
        analyze_text_local(
            text=item.text,
            title=item.title,
            publisher=item.publisher,
            published_at=published_at,
            meta={"demo": True, "scenario": item.scenario, "synthetic": True},
        )
        created += 1

    logger.info("demo_seeded", extra={"extra_fields": {"analyses": created}})
    return created
