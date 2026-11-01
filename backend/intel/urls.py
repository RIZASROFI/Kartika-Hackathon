from django.urls import path

from intel.views import (
    AnalysisBulkDeleteView,
    AnalysisDetailView,
    AnalysisListCreateView,
    DashboardSummaryView,
)

urlpatterns = [
    path("analyses", AnalysisListCreateView.as_view(), name="analysis-list"),
    path(
        "analyses/bulk-delete",
        AnalysisBulkDeleteView.as_view(),
        name="analysis-bulk-delete",
    ),
    path(
        "analyses/<str:analysis_id>",
        AnalysisDetailView.as_view(),
        name="analysis-detail",
    ),
    path(
        "dashboard/summary",
        DashboardSummaryView.as_view(),
        name="dashboard-summary",
    ),
]
