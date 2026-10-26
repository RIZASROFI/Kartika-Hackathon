"""View API dan penyajian frontend React."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db.models import Prefetch
from django.http import FileResponse, JsonResponse
from django.views.decorators.http import require_GET
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from intel.models import Analysis, CoordinationLink
from intel.serializers import (
    AnalysisCreateSerializer,
    AnalysisDetailSerializer,
    AnalysisListItemSerializer,
)
from intel.services.analysis_service import create_analysis
from intel.services.dashboard_service import build_dashboard
from intel.services.extraction import ExtractionError


def _detail_queryset():
    return Analysis.objects.select_related("content").prefetch_related(
        "signals",
        "claims",
        "evidence",
        Prefetch(
            "links",
            queryset=CoordinationLink.objects.select_related(
                "related_analysis__content"
            ),
        ),
    )


class AnalysisListCreateView(APIView):
    def get(self, request):
        try:
            limit = int(request.query_params.get("limit", 20))
            offset = int(request.query_params.get("offset", 0))
        except (TypeError, ValueError):
            return Response(
                {"detail": "Parameter limit/offset harus berupa angka."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not 1 <= limit <= 100 or offset < 0:
            return Response(
                {"detail": "limit harus 1–100 dan offset tidak boleh negatif."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        queryset = Analysis.objects.select_related("content")
        verdict = request.query_params.get("verdict")
        category = request.query_params.get("category")
        if verdict:
            queryset = queryset.filter(verdict=verdict)
        if category:
            queryset = queryset.filter(signals__category=category).distinct()

        analyses = queryset.order_by("-created_at")[offset : offset + limit]
        return Response(AnalysisListItemSerializer(analyses, many=True).data)

    def post(self, request):
        serializer = AnalysisCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            analysis = create_analysis(**serializer.validated_data)
        except ExtractionError as exc:
            return Response(
                {"detail": exc.message}, status=exc.status_code
            )

        detailed = _detail_queryset().filter(pk=analysis.pk).first()
        return Response(
            AnalysisDetailSerializer(detailed).data,
            status=status.HTTP_201_CREATED,
        )


class AnalysisDetailView(APIView):
    def get(self, request, analysis_id: str):
        try:
            uuid.UUID(str(analysis_id))
        except (ValueError, TypeError) as exc:
            raise NotFound("Analisis tidak ditemukan.") from exc

        analysis = _detail_queryset().filter(pk=analysis_id).first()
        if analysis is None:
            raise NotFound("Analisis tidak ditemukan.")
        return Response(AnalysisDetailSerializer(analysis).data)


class DashboardSummaryView(APIView):
    def get(self, request):
        return Response(build_dashboard())


@require_GET
def health_view(request):
    return JsonResponse(
        {
            "status": "ok",
            "service": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
        }
    )


def spa_view(request, path: str = ""):
    """Sajikan hasil build React, termasuk deep link React Router."""
    if path.startswith("api/") or path == "health":
        return JsonResponse({"detail": "Not Found"}, status=404)

    dist = settings.FRONTEND_DIST
    dist_root = dist.resolve()

    if path:
        candidate = (dist / path).resolve()
        try:
            candidate.relative_to(dist_root)
        except ValueError:
            candidate = None
        if candidate is not None and candidate.is_file():
            response = FileResponse(candidate.open("rb"))
            if path.startswith("assets/"):
                response["Cache-Control"] = "public, max-age=31536000, immutable"
            return response

    index_file = dist / "index.html"
    if index_file.is_file():
        return FileResponse(index_file.open("rb"), content_type="text/html")

    return JsonResponse(
        {"detail": "Frontend belum dibangun. Jalankan: npm run build"}, status=404
    )
