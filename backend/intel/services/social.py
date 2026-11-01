"""Ingest satu postingan media sosial publik lewat UnifAPI.

Modul ini mengambil teks/caption, penulis, waktu unggah, dan metrik interaksi
dari postingan publik TikTok, Instagram, Facebook, atau X/Twitter. Yang diambil
hanya isi satu postingan — bukan jaringan penyebaran atau metadata akun lain.

Pemanggilan jaringan tidak boleh menggagalkan analisis diam-diam: setiap
kegagalan dipetakan menjadi ``SocialFetchError`` dengan pesan berbahasa
Indonesia agar dapat ditampilkan langsung oleh API.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from urllib.parse import urlparse

import httpx
from django.conf import settings

from intel.analysis.text_stats import normalize_whitespace, word_count

logger = logging.getLogger(__name__)

PLATFORM_LABELS = {
    "tiktok": "TikTok",
    "instagram": "Instagram",
    "facebook": "Facebook",
    "x": "X/Twitter",
}

PLATFORM_DOMAINS = {
    "tiktok": ("tiktok.com",),
    "instagram": ("instagram.com", "instagr.am"),
    "facebook": ("facebook.com", "fb.com", "fb.watch"),
    "x": ("twitter.com", "x.com"),
}

MAX_TITLE_CHARS = 140
MIN_TEXT_WORDS = 8

_INSTAGRAM_PATH_KINDS = {"p", "reel", "reels", "tv"}
_X_STATUS_PATTERN = re.compile(r"/status(?:es)?/(\d+)")


class SocialFetchError(Exception):
    def __init__(self, message: str, *, status_code: int = 422) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass
class SocialPost:
    platform: str
    url: str
    canonical_url: str | None
    text: str
    title: str | None
    author: str | None
    publisher: str | None
    published_at: datetime | None = None
    meta: dict = field(default_factory=dict)


def _host(url: str) -> str:
    host = (urlparse(url).hostname or "").casefold().rstrip(".")
    for prefix in ("www.", "m.", "mobile.", "web."):
        if host.startswith(prefix):
            host = host[len(prefix) :]
    return host


def detect_platform(url: str) -> str | None:
    """Kembalikan platform media sosial dari URL, atau ``None`` bila bukan."""
    host = _host(url.strip())
    if not host:
        return None
    for platform, domains in PLATFORM_DOMAINS.items():
        if any(host == domain or host.endswith(f".{domain}") for domain in domains):
            return platform
    return None


def _instagram_shortcode(url: str) -> str | None:
    parts = [part for part in urlparse(url).path.split("/") if part]
    for index, part in enumerate(parts):
        if part in _INSTAGRAM_PATH_KINDS and index + 1 < len(parts):
            return parts[index + 1]
    return None


def _x_post_id(url: str) -> str | None:
    match = _X_STATUS_PATTERN.search(urlparse(url).path)
    return match.group(1) if match else None


def _as_http_url(value: str | None) -> str | None:
    if isinstance(value, str) and value.startswith(("http://", "https://")):
        return value
    return None


def _parse_epoch(value) -> datetime | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        return datetime.fromtimestamp(value, tz=UTC)
    except (OverflowError, OSError, ValueError):
        return None


def _parse_moment(value) -> datetime | None:
    """Terima unix epoch atau timestamp ISO 8601 dari respons penyedia."""
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        if cleaned.isdigit():
            return _parse_epoch(int(cleaned))
        try:
            parsed = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
    return _parse_epoch(value)


def _api_get(path: str, params: dict | None = None) -> dict:
    api_key = settings.UNIFAPI_API_KEY
    if not api_key:
        raise SocialFetchError(
            "Kunci API media sosial (UNIFAPI_API_KEY) belum diatur. Isi kunci "
            "tersebut atau tempelkan teks postingan secara manual."
        )

    try:
        with httpx.Client(
            timeout=settings.SOCIAL_FETCH_TIMEOUT_SECONDS,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
            },
        ) as client:
            response = client.get(
                f"{settings.UNIFAPI_BASE_URL}{path}", params=params or {}
            )
    except httpx.HTTPError as exc:
        logger.warning(
            "social_fetch_failed",
            extra={"extra_fields": {"path": path, "error": exc.__class__.__name__}},
        )
        raise SocialFetchError(
            "Gagal menghubungi layanan data media sosial. Periksa koneksi jaringan.",
            status_code=502,
        ) from exc

    if response.status_code in {401, 403}:
        raise SocialFetchError(
            "Layanan data media sosial menolak kredensial. Periksa UNIFAPI_API_KEY.",
            status_code=502,
        )
    if response.status_code == 404:
        raise SocialFetchError("Postingan tidak ditemukan atau bukan postingan publik.")
    if response.status_code == 429:
        raise SocialFetchError(
            "Kuota layanan data media sosial habis. Coba lagi nanti atau "
            "tempelkan teks postingan secara manual.",
            status_code=502,
        )
    if response.status_code >= 500:
        raise SocialFetchError(
            "Layanan data media sosial sedang bermasalah. Coba lagi nanti.",
            status_code=502,
        )
    if response.status_code >= 400:
        raise SocialFetchError(
            f"Layanan data media sosial menolak permintaan (HTTP {response.status_code})."
        )

    try:
        body = response.json()
    except ValueError as exc:
        raise SocialFetchError(
            "Respons layanan data media sosial bukan JSON yang valid.",
            status_code=502,
        ) from exc

    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, dict):
        raise SocialFetchError(
            "Respons layanan data media sosial tidak dikenali.", status_code=502
        )
    return data


def _engagement(**values) -> dict:
    return {
        key: int(value)
        for key, value in values.items()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    }


def _title_from_text(text: str) -> str | None:
    cleaned = normalize_whitespace(text)
    if not cleaned:
        return None
    if len(cleaned) <= MAX_TITLE_CHARS:
        return cleaned
    return f"{cleaned[: MAX_TITLE_CHARS - 1].rstrip()}…"


def _publisher(platform: str, handle: str | None) -> str:
    label = PLATFORM_LABELS.get(platform, platform)
    return f"{label} · @{handle}" if handle else label


def _normalize_tiktok(data: dict, url: str) -> SocialPost:
    from_tiktok = data.get("author") or {}
    handle = normalize_whitespace(str(from_tiktok.get("username") or "")) or None
    author = (
        normalize_whitespace(
            str(from_tiktok.get("display_name") or from_tiktok.get("username") or "")
        )
        or None
    )
    text = normalize_whitespace(
        str(data.get("video_description") or data.get("title") or "")
    )
    canonical = _as_http_url(data.get("share_url"))
    return SocialPost(
        platform="tiktok",
        url=url,
        canonical_url=canonical,
        text=text,
        title=_title_from_text(text),
        author=author,
        publisher=_publisher("tiktok", handle),
        published_at=_parse_moment(data.get("create_time")),
        meta={
            "platform": "tiktok",
            "post_id": str(data.get("id") or "") or None,
            "author_handle": handle,
            "media_url": _as_http_url(data.get("cover_image_url")),
            "engagement": _engagement(
                like_count=data.get("like_count"),
                comment_count=data.get("comment_count"),
                share_count=data.get("share_count"),
                view_count=data.get("view_count"),
            ),
        },
    )


def _normalize_instagram(data: dict, url: str) -> SocialPost:
    from_instagram = data.get("user") or {}
    handle = normalize_whitespace(str(from_instagram.get("username") or "")) or None
    author = (
        normalize_whitespace(
            str(from_instagram.get("full_name") or from_instagram.get("username") or "")
        )
        or None
    )
    text = normalize_whitespace(
        str(data.get("caption") or data.get("accessibility_caption") or "")
    )
    shortcode = str(data.get("shortcode") or data.get("id") or "").strip()
    canonical = (
        f"https://www.instagram.com/p/{shortcode}/" if shortcode else None
    )
    return SocialPost(
        platform="instagram",
        url=url,
        canonical_url=canonical,
        text=text,
        title=_title_from_text(text),
        author=author,
        publisher=_publisher("instagram", handle),
        published_at=_parse_moment(data.get("taken_at")),
        meta={
            "platform": "instagram",
            "post_id": str(data.get("media_id") or shortcode or "") or None,
            "author_handle": handle,
            "media_url": _as_http_url(
                data.get("image_url") or data.get("video_url")
            ),
            "engagement": _engagement(
                like_count=data.get("like_count"),
                comment_count=data.get("comment_count"),
                view_count=data.get("view_count"),
                play_count=data.get("play_count"),
            ),
        },
    )


def _normalize_facebook(data: dict, url: str) -> SocialPost:
    from_facebook = data.get("author") or {}
    author = normalize_whitespace(str(from_facebook.get("name") or "")) or None
    text = normalize_whitespace(str(data.get("description") or ""))
    media = data.get("media") or {}
    return SocialPost(
        platform="facebook",
        url=url,
        canonical_url=_as_http_url(data.get("url")),
        text=text,
        title=_title_from_text(text),
        author=author,
        publisher=f"Facebook · {author}" if author else "Facebook",
        published_at=_parse_moment(data.get("published_at")),
        meta={
            "platform": "facebook",
            "post_id": str(data.get("post_id") or "") or None,
            "author_handle": None,
            "author_url": _as_http_url(from_facebook.get("profile_url")),
            "media_url": _as_http_url(
                media.get("image_url") or media.get("thumbnail_url")
            ),
            "engagement": _engagement(
                like_count=data.get("like_count"),
                comment_count=data.get("comment_count"),
                share_count=data.get("share_count"),
                view_count=data.get("view_count"),
            ),
        },
    )


def _normalize_x(data: dict, url: str) -> SocialPost:
    from_x = data.get("author") or {}
    handle = normalize_whitespace(str(from_x.get("username") or "")) or None
    author = (
        normalize_whitespace(str(from_x.get("name") or from_x.get("username") or ""))
        or None
    )
    text = normalize_whitespace(str(data.get("text") or ""))
    post_id = str(data.get("id") or "").strip()
    canonical = (
        f"https://x.com/{handle}/status/{post_id}" if handle and post_id else None
    )
    metrics = data.get("public_metrics") or {}
    return SocialPost(
        platform="x",
        url=url,
        canonical_url=canonical,
        text=text,
        title=_title_from_text(text),
        author=author,
        publisher=_publisher("x", handle),
        published_at=_parse_moment(data.get("created_at")),
        meta={
            "platform": "x",
            "post_id": post_id or None,
            "author_handle": handle,
            "author_url": f"https://x.com/{handle}" if handle else None,
            "engagement": _engagement(
                like_count=metrics.get("like_count"),
                reply_count=metrics.get("reply_count"),
                repost_count=metrics.get("retweet_count"),
                quote_count=metrics.get("quote_count"),
                view_count=metrics.get("impression_count"),
            ),
        },
    )


def fetch_social_post(url: str, *, platform: str | None = None) -> SocialPost:
    """Ambil dan normalkan satu postingan publik. Melempar SocialFetchError."""
    url = url.strip()
    platform = platform or detect_platform(url)
    if platform is None:
        raise SocialFetchError("URL bukan tautan media sosial yang didukung.")

    if platform == "tiktok":
        post = _normalize_tiktok(
            _api_get("/tiktok/videos/resolve", {"url": url}), url
        )
    elif platform == "instagram":
        shortcode = _instagram_shortcode(url)
        if not shortcode:
            raise SocialFetchError(
                "Tautan Instagram harus menunjuk ke postingan (/p/, /reel/, atau /tv/)."
            )
        post = _normalize_instagram(
            _api_get(f"/instagram/posts/{shortcode}"), url
        )
    elif platform == "facebook":
        post = _normalize_facebook(
            _api_get("/facebook/posts", {"url": url}), url
        )
    elif platform == "x":
        post_id = _x_post_id(url)
        if not post_id:
            raise SocialFetchError(
                "Tautan X/Twitter harus menunjuk ke postingan (/status/<id>)."
            )
        post = _normalize_x(
            _api_get(
                f"/x/tweets/{post_id}",
                {
                    "expansions": "author_id",
                    "tweet.fields": "created_at,text,lang,public_metrics",
                    "user.fields": "name,username",
                },
            ),
            url,
        )
    else:  # pragma: no cover - dijaga oleh detect_platform
        raise SocialFetchError("Platform media sosial tidak didukung.")

    post.text = post.text[: settings.MAX_CONTENT_CHARS]
    if word_count(post.text) < MIN_TEXT_WORDS:
        raise SocialFetchError(
            f"Teks postingan hanya {word_count(post.text)} kata; minimal "
            f"{MIN_TEXT_WORDS} kata agar sinyal dapat dihitung. Tempelkan teks "
            "lengkap secara manual bila caption terlalu pendek."
        )
    return post
