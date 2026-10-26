"""Ekstraksi konten artikel dari URL dengan pengamanan SSRF dasar."""

from __future__ import annotations

import ipaddress
import logging
import socket
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from django.conf import settings

from intel.analysis.text_stats import normalize_whitespace

logger = logging.getLogger(__name__)

USER_AGENT = (
    "KARTIKAIntelBot/0.1 (+https://example.org/kartika-intel; riset keamanan informasi)"
)
MAX_HTML_BYTES = 3_000_000
BLOCKED_HOST_SUFFIXES = (".local", ".internal", ".localhost", "localhost")
NAVIGATION_LABELS = {
    "lompat ke isi",
    "halaman utama",
    "daftar isi",
    "perubahan terbaru",
    "artikel pilihan",
    "sumbangan",
    "buat akun",
    "masuk",
    "unduh",
    "sunting",
    "lihat riwayat",
    "kebijakan privasi",
    "tentang wikipedia",
    "penyangkalan",
    "bantuan",
    "donasi",
    "beranda",
    "home",
    "login",
    "sign in",
    "subscribe",
    "menu",
    "bagikan",
    "share",
}


class ExtractionError(Exception):
    def __init__(self, message: str, *, status_code: int = 422) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass
class ExtractedArticle:
    url: str
    canonical_url: str
    title: str | None
    author: str | None
    publisher: str | None
    text: str
    published_at: datetime | None = None
    links: list[dict[str, str]] = field(default_factory=list)


def _ensure_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ExtractionError("Hanya URL http/https yang didukung.")
    host = (parsed.hostname or "").lower()
    if not host:
        raise ExtractionError("URL tidak memiliki host yang valid.")
    if host in BLOCKED_HOST_SUFFIXES or host.endswith(BLOCKED_HOST_SUFFIXES):
        raise ExtractionError("Host internal tidak diizinkan.")

    try:
        addresses = {info[4][0] for info in socket.getaddrinfo(host, None)}
    except socket.gaierror as exc:
        raise ExtractionError("Host tidak dapat diresolusi.", status_code=400) from exc

    for address in addresses:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            continue
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise ExtractionError("Alamat IP internal/private tidak diizinkan.")


def _parse_published_at(value: str | None) -> datetime | None:
    if not value:
        return None
    cleaned = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(cleaned)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    else:
        parsed = parsed.astimezone(timezone.utc)
    return parsed


def _extract_links(soup: BeautifulSoup, base_url: str) -> list[dict[str, str]]:
    """Ambil tautan referensi, memprioritaskan tautan di dalam paragraf."""
    paragraph_anchors = [
        anchor for paragraph in soup.find_all("p") for anchor in paragraph.find_all("a", href=True)
    ]
    candidates = paragraph_anchors + soup.find_all("a", href=True)

    links: list[dict[str, str]] = []
    seen: set[str] = set()
    base_clean = base_url.split("#", 1)[0]
    for anchor in candidates:
        raw_href = (anchor.get("href") or "").strip()
        if not raw_href or raw_href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        href = urljoin(base_url, raw_href).split("#", 1)[0]
        if not href.startswith(("http://", "https://")) or href in seen or href == base_clean:
            continue
        label = normalize_whitespace(anchor.get_text(" ", strip=True))[:160]
        if not label or not any(char.isalpha() for char in label):
            continue
        if label.lower().strip(" .·") in NAVIGATION_LABELS:
            continue
        seen.add(href)
        links.append({"url": href, "title": label})
        if len(links) >= 5:
            break
    return links


def _trafilatura_text(html: str, url: str) -> str:
    try:
        import trafilatura
    except ImportError:  # pragma: no cover - dependensi opsional saat runtime
        return ""
    extracted = trafilatura.extract(
        html,
        url=url,
        include_comments=False,
        include_tables=False,
        favor_recall=True,
        deduplicate=True,
    )
    return normalize_whitespace(extracted or "")


def _metadata_from_trafilatura(html: str, url: str) -> dict[str, str | None]:
    try:
        import trafilatura
    except ImportError:  # pragma: no cover
        return {}
    try:
        metadata = trafilatura.extract_metadata(html, default_url=url)
    except Exception:  # pragma: no cover - metadata bersifat best effort
        return {}
    if metadata is None:
        return {}
    return {
        "title": metadata.title,
        "author": metadata.author,
        "publisher": metadata.sitename,
        "date": metadata.date,
    }


def extract_article(url: str) -> ExtractedArticle:
    url = url.strip()
    _ensure_public_url(url)

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "id,en;q=0.8",
    }
    try:
        with httpx.Client(
            timeout=settings.FETCH_TIMEOUT_SECONDS,
            follow_redirects=True,
            headers=headers,
        ) as client:
            response = client.get(url)
    except httpx.HTTPError as exc:
        logger.warning(
            "fetch_failed", extra={"extra_fields": {"url": url, "error": str(exc)}}
        )
        raise ExtractionError(
            "Gagal mengambil artikel. Periksa URL atau koneksi jaringan.", status_code=502
        ) from exc

    if response.status_code >= 400:
        raise ExtractionError(
            f"Sumber menolak permintaan (HTTP {response.status_code}).", status_code=502
        )
    if "html" not in response.headers.get("content-type", ""):
        raise ExtractionError("Konten sumber bukan halaman HTML.")

    _ensure_public_url(str(response.url))

    html = response.text
    if len(html.encode("utf-8", errors="ignore")) > MAX_HTML_BYTES:
        raise ExtractionError("Halaman terlalu besar untuk dianalisis.")

    soup = BeautifulSoup(html, "html.parser")

    metadata = _metadata_from_trafilatura(html, url)
    page_title = normalize_whitespace(
        metadata.get("title")
        or (soup.title.get_text(strip=True) if soup.title else "")
        or ""
    )
    if not page_title:
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            page_title = normalize_whitespace(og_title["content"])

    author = metadata.get("author") or None
    if not author:
        author_meta = soup.find("meta", attrs={"name": "author"})
        if author_meta and author_meta.get("content"):
            author = normalize_whitespace(author_meta["content"])[:256]

    published_raw = metadata.get("date")
    if not published_raw:
        for selector in (
            {"property": "article:published_time"},
            {"name": "date"},
            {"name": "publish-date"},
        ):
            tag = soup.find("meta", attrs=selector)
            if tag and tag.get("content"):
                published_raw = tag["content"]
                break

    publisher = metadata.get("publisher") or urlparse(str(response.url)).hostname
    if not publisher:
        site_name = soup.find("meta", property="og:site_name")
        if site_name and site_name.get("content"):
            publisher = normalize_whitespace(site_name["content"])[:256]
    publisher = normalize_whitespace(publisher or "")[:256] or None

    text = _trafilatura_text(html, str(response.url))
    if len(text.split()) < 30:
        paragraphs = [
            normalize_whitespace(paragraph.get_text(" ", strip=True))
            for paragraph in soup.find_all("p")
        ]
        fallback = normalize_whitespace(
            " ".join(paragraph for paragraph in paragraphs if paragraph)
        )
        if len(fallback.split()) > len(text.split()):
            text = fallback

    text = text[: settings.MAX_CONTENT_CHARS]
    if len(text.split()) < 20:
        raise ExtractionError(
            "Isi artikel tidak dapat diekstrak secara memadai. Tempelkan teks secara manual."
        )

    return ExtractedArticle(
        url=url,
        canonical_url=str(response.url),
        title=page_title[:512] or None,
        author=author,
        publisher=publisher,
        text=text,
        published_at=_parse_published_at(published_raw),
        links=_extract_links(soup, str(response.url)),
    )
