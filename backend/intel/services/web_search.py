"""Pencarian sumber terbuka (Exa) untuk mendukung verifikasi klaim.

Modul ini hanya melakukan *retrieval*: mengambil cuplikan halaman yang dapat
disitasi. Penilaian dilakukan terpisah oleh model bahasa agar setiap langkah
dapat diaudit dan kegagalan jaringan tidak pernah menggagalkan analisis.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from urllib.parse import urlparse

import httpx
from django.conf import settings

from intel.analysis.text_stats import normalize_whitespace

logger = logging.getLogger(__name__)

MAX_QUERY_CHARS = 400
MAX_TITLE_CHARS = 512


class SearchError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass
class WebEvidence:
    title: str
    url: str
    publisher: str
    snippet: str
    published_date: str | None = None
    query: str = ""

    def to_json(self) -> dict:
        return asdict(self)


def _publisher(url: str) -> str:
    host = (urlparse(url).netloc or "").casefold()
    return host[4:] if host.startswith("www.") else host


def _snippet(result: dict) -> str:
    highlights = result.get("highlights")
    if isinstance(highlights, list):
        joined = normalize_whitespace(" ".join(str(item) for item in highlights if item))
        if joined:
            return joined[: settings.EXA_SNIPPET_CHARS]
    text = result.get("text")
    if isinstance(text, str) and text.strip():
        return normalize_whitespace(text)[: settings.EXA_SNIPPET_CHARS]
    return ""


def _parse_results(payload: dict, *, claim: str) -> list[WebEvidence]:
    results = payload.get("results")
    if not isinstance(results, list):
        return []

    evidence: list[WebEvidence] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        url = (item.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            continue
        title = normalize_whitespace(item.get("title") or url)[:MAX_TITLE_CHARS]
        evidence.append(
            WebEvidence(
                title=title,
                url=url,
                publisher=_publisher(url)[:256],
                snippet=_snippet(item),
                published_date=item.get("publishedDate"),
                query=claim,
            )
        )
    return evidence


def search_web(claim: str, *, limit: int | None = None) -> list[WebEvidence]:
    """Cari sumber terbuka untuk satu klaim. Melempar SearchError saat gagal."""
    query = normalize_whitespace(claim)[:MAX_QUERY_CHARS]
    if not query:
        return []
    if not settings.EXA_API_KEY:
        raise SearchError("API key pencarian web (EXA_API_KEY) belum diatur.")

    payload = {
        "query": query,
        "numResults": limit or max(1, settings.EXA_RESULTS_PER_CLAIM),
        "type": "auto",
        "contents": {
            "highlights": True,
            "text": {"maxCharacters": settings.EXA_SNIPPET_CHARS},
        },
    }

    try:
        with httpx.Client(timeout=settings.EXA_TIMEOUT_SECONDS) as client:
            response = client.post(
                f"{settings.EXA_BASE_URL}/search",
                json=payload,
                headers={
                    "x-api-key": settings.EXA_API_KEY,
                    "Content-Type": "application/json",
                },
            )
    except httpx.HTTPError as exc:
        raise SearchError(
            f"Koneksi ke layanan pencarian web gagal: {exc.__class__.__name__}."
        ) from exc

    if response.status_code in {401, 403}:
        raise SearchError(
            "API key pencarian web ditolak atau kuota akun tidak aktif "
            f"(HTTP {response.status_code}).",
            status_code=response.status_code,
        )
    if response.status_code == 429:
        raise SearchError(
            "Kuota pencarian web habis (HTTP 429). Coba lagi nanti.",
            status_code=429,
        )
    if response.status_code >= 400:
        raise SearchError(
            f"Layanan pencarian web mengembalikan HTTP {response.status_code}.",
            status_code=response.status_code,
        )

    try:
        body = response.json()
    except ValueError as exc:
        raise SearchError("Respons pencarian web bukan JSON yang valid.") from exc
    if not isinstance(body, dict):
        raise SearchError("Respons pencarian web tidak dikenali.")

    return _parse_results(body, claim=query)
