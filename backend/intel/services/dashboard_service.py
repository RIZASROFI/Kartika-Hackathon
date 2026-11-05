"""Agregasi data dashboard intelijen."""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from django.db.models import Avg, Count, Max, Q
from django.utils import timezone

from intel.analysis.ebde import (
    VERDICT_BELUM_DAPAT_DINILAI,
    VERDICT_CAMPURAN,
    VERDICT_PERLU_VERIFIKASI,
    VERDICT_TERINDIKASI_FAKTA,
    VERDICT_TERINDIKASI_HOAKS,
)
from intel.analysis.pipeline import VERDICT_LABELS
from intel.models import Analysis, AnalysisSignal, Claim, ContentItem
from intel.serializers import AnalysisListItemSerializer

CATEGORY_LABELS = {
    "hoax": "Hoax & Fakta",
    "indobert": "Model IndoBERT",
}
VERDICT_ORDER = [
    VERDICT_TERINDIKASI_HOAKS,
    VERDICT_TERINDIKASI_FAKTA,
    VERDICT_CAMPURAN,
    VERDICT_PERLU_VERIFIKASI,
    VERDICT_BELUM_DAPAT_DINILAI,
    # Format lama tetap muncul selama riwayat lama belum dimigrasikan.
    "terindikasi_menyesatkan",
    "risiko_rendah",
]
TREND_DAYS = 14


def _iso(value) -> str | None:
    if value is None:
        return None
    return value.isoformat().replace("+00:00", "Z")


def build_dashboard() -> dict:
    now = timezone.now()

    total_analyses = Analysis.objects.count()
    total_contents = ContentItem.objects.count()
    total_claims = Claim.objects.count()
    aggregates = Analysis.objects.aggregate(
        average_risk=Avg("risk_score"),
        high_risk=Count("id", filter=Q(risk_score__gte=50)),
    )

    verdict_rows = (
        Analysis.objects.values("verdict").annotate(count=Count("id")).order_by()
    )
    verdict_counts = {row["verdict"]: row["count"] for row in verdict_rows}
    verdict_distribution = [
        {
            "verdict": verdict,
            "label": VERDICT_LABELS.get(verdict, verdict),
            "count": verdict_counts.get(verdict, 0),
        }
        for verdict in VERDICT_ORDER
        if verdict_counts.get(verdict, 0) > 0
    ]

    start_day = (now - timedelta(days=TREND_DAYS - 1)).date()
    trend_rows = Analysis.objects.filter(
        created_at__gte=now - timedelta(days=TREND_DAYS)
    ).values_list("created_at", "risk_score")
    buckets: dict = defaultdict(list)
    for created_at, risk_score in trend_rows:
        buckets[created_at.date()].append(risk_score)

    risk_trend = []
    for offset in range(TREND_DAYS):
        day = start_day + timedelta(days=offset)
        scores = buckets.get(day, [])
        risk_trend.append(
            {
                "date": day.isoformat(),
                "analyses": len(scores),
                "average_risk": round(sum(scores) / len(scores), 1) if scores else 0.0,
                "high_risk": sum(1 for score in scores if score >= 50),
            }
        )

    category_rows = (
        AnalysisSignal.objects.values("category")
        .annotate(average_score=Avg("score"), max_score=Max("score"))
        .order_by()
    )
    category_scores = [
        {
            "category": row["category"],
            "label": CATEGORY_LABELS.get(row["category"], row["category"]),
            "average_score": round(float(row["average_score"] or 0), 1),
            "max_score": int(row["max_score"] or 0),
        }
        for row in category_rows
    ]

    recent = Analysis.objects.select_related("content").order_by("-created_at")[:6]
    recent_analyses = AnalysisListItemSerializer(recent, many=True).data

    return {
        "generated_at": _iso(now),
        "totals": {
            "analyses": total_analyses,
            "contents": total_contents,
            "high_risk": aggregates["high_risk"] or 0,
            "average_risk": round(float(aggregates["average_risk"] or 0), 1),
            "claims": total_claims,
        },
        "verdict_distribution": verdict_distribution,
        "risk_trend": risk_trend,
        "category_scores": category_scores,
        "recent_analyses": recent_analyses,
    }
