from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from intel.services.social import (
    SocialFetchError,
    SocialPost,
    detect_platform,
    fetch_social_post,
)

SOCIAL_TEXT = (
    "Pemerintah akan memadamkan listrik nasional selama tiga hari mulai besok. "
    "Sebarkan pesan ini sebelum dihapus pihak berwenang."
)


class DetectPlatformTests(TestCase):
    def test_supported_platforms(self) -> None:
        cases = {
            "https://www.tiktok.com/@akun/video/123": "tiktok",
            "https://vm.tiktok.com/ZS123ABC/": "tiktok",
            "https://www.instagram.com/p/DUajw4YkorV/": "instagram",
            "https://instagram.com/reel/DUajw4YkorV/": "instagram",
            "https://m.facebook.com/story.php?story_fbid=1&id=2": "facebook",
            "https://fb.watch/abc123/": "facebook",
            "https://twitter.com/akun/status/123": "x",
            "https://x.com/akun/status/123": "x",
        }
        for url, expected in cases.items():
            self.assertEqual(detect_platform(url), expected, url)

    def test_non_social_urls(self) -> None:
        for url in (
            "https://contoh.id/artikel/berita",
            "https://notx.com/akun/status/123",
            "https://instagram.com.evil.example/p/abc/",
            "bukan-url",
        ):
            self.assertIsNone(detect_platform(url), url)


@override_settings(UNIFAPI_API_KEY="kunci-uji")
class NormalizationTests(TestCase):
    def test_tiktok_post_is_normalized(self) -> None:
        payload = {
            "id": "7412345678901234567",
            "title": "Listrik padam tiga hari",
            "video_description": SOCIAL_TEXT,
            "create_time": 1735689600,
            "share_url": "https://www.tiktok.com/@akun/video/7412345678901234567",
            "cover_image_url": "https://cdn.example/cover.jpg",
            "like_count": 1200,
            "comment_count": 45,
            "share_count": 300,
            "view_count": 90000,
            "author": {
                "id": "user-1",
                "username": "akun",
                "display_name": "Akun Uji",
            },
        }
        with patch("intel.services.social._api_get", return_value=payload) as api_get:
            post = fetch_social_post(
                "https://www.tiktok.com/@akun/video/7412345678901234567"
            )

        api_get.assert_called_once_with(
            "/tiktok/videos/resolve",
            {"url": "https://www.tiktok.com/@akun/video/7412345678901234567"},
        )
        self.assertEqual(post.platform, "tiktok")
        self.assertEqual(post.text, SOCIAL_TEXT)
        self.assertEqual(post.author, "Akun Uji")
        self.assertEqual(post.publisher, "TikTok · @akun")
        self.assertEqual(post.canonical_url, payload["share_url"])
        self.assertEqual(post.published_at, datetime(2025, 1, 1, tzinfo=UTC))
        self.assertEqual(post.meta["author_handle"], "akun")
        self.assertEqual(post.meta["engagement"]["like_count"], 1200)

    def test_instagram_post_is_normalized(self) -> None:
        payload = {
            "id": "DUajw4YkorV",
            "shortcode": "DUajw4YkorV",
            "media_id": "987654321",
            "taken_at": 1735689600,
            "caption": SOCIAL_TEXT,
            "image_url": "https://cdn.example/image.jpg",
            "like_count": 88,
            "comment_count": 7,
            "user": {"username": "akunig", "full_name": "Akun Instagram"},
        }
        with patch("intel.services.social._api_get", return_value=payload) as api_get:
            post = fetch_social_post("https://www.instagram.com/p/DUajw4YkorV/")

        api_get.assert_called_once_with("/instagram/posts/DUajw4YkorV")
        self.assertEqual(post.platform, "instagram")
        self.assertEqual(post.text, SOCIAL_TEXT)
        self.assertEqual(post.author, "Akun Instagram")
        self.assertEqual(post.publisher, "Instagram · @akunig")
        self.assertEqual(
            post.canonical_url, "https://www.instagram.com/p/DUajw4YkorV/"
        )
        self.assertEqual(post.published_at, datetime(2025, 1, 1, tzinfo=UTC))

    def test_facebook_post_is_normalized(self) -> None:
        payload = {
            "platform": "facebook",
            "post_id": "123_456",
            "url": "https://www.facebook.com/akun/posts/456",
            "description": SOCIAL_TEXT,
            "published_at": "2026-10-20T10:00:00+00:00",
            "like_count": 10,
            "comment_count": 2,
            "share_count": 3,
            "author": {"name": "Halaman Uji", "profile_url": "https://facebook.com/akun"},
        }
        with patch("intel.services.social._api_get", return_value=payload) as api_get:
            post = fetch_social_post(
                "https://www.facebook.com/akun/posts/456"
            )

        api_get.assert_called_once_with(
            "/facebook/posts", {"url": "https://www.facebook.com/akun/posts/456"}
        )
        self.assertEqual(post.platform, "facebook")
        self.assertEqual(post.text, SOCIAL_TEXT)
        self.assertEqual(post.author, "Halaman Uji")
        self.assertEqual(post.publisher, "Facebook · Halaman Uji")
        self.assertEqual(post.published_at, datetime(2026, 10, 20, 10, tzinfo=UTC))
        self.assertEqual(post.meta["post_id"], "123_456")

    def test_x_post_is_normalized(self) -> None:
        payload = {
            "id": "1234567890",
            "text": SOCIAL_TEXT,
            "created_at": "2026-10-20T10:00:00.000Z",
            "lang": "id",
            "public_metrics": {
                "like_count": 50,
                "reply_count": 5,
                "retweet_count": 12,
                "quote_count": 1,
                "impression_count": 4000,
            },
            "author": {"name": "Akun X", "username": "akunx"},
        }
        with patch("intel.services.social._api_get", return_value=payload) as api_get:
            post = fetch_social_post("https://x.com/akunx/status/1234567890")

        path = api_get.call_args.args[0]
        params = api_get.call_args.args[1]
        self.assertEqual(path, "/x/tweets/1234567890")
        self.assertEqual(params["expansions"], "author_id")
        self.assertEqual(post.platform, "x")
        self.assertEqual(post.author, "Akun X")
        self.assertEqual(post.publisher, "X/Twitter · @akunx")
        self.assertEqual(
            post.canonical_url, "https://x.com/akunx/status/1234567890"
        )
        self.assertEqual(post.meta["engagement"]["repost_count"], 12)

    def test_short_caption_is_rejected(self) -> None:
        payload = {"caption": "Hanya tiga kata", "user": {"username": "akun"}}
        with patch("intel.services.social._api_get", return_value=payload):
            with self.assertRaises(SocialFetchError) as raised:
                fetch_social_post("https://www.instagram.com/p/DUajw4YkorV/")
        self.assertIn("minimal 8 kata", raised.exception.message)

    def test_instagram_url_without_shortcode_is_rejected(self) -> None:
        with self.assertRaises(SocialFetchError):
            fetch_social_post("https://www.instagram.com/akun/")

    def test_x_url_without_status_id_is_rejected(self) -> None:
        with self.assertRaises(SocialFetchError):
            fetch_social_post("https://x.com/akun")


class MissingKeyTests(TestCase):
    @override_settings(UNIFAPI_API_KEY="")
    def test_missing_key_has_actionable_message(self) -> None:
        with self.assertRaises(SocialFetchError) as raised:
            fetch_social_post("https://www.tiktok.com/@akun/video/123")
        self.assertIn("UNIFAPI_API_KEY", raised.exception.message)
        self.assertEqual(raised.exception.status_code, 422)

    def test_unsupported_url_is_rejected(self) -> None:
        with self.assertRaises(SocialFetchError):
            fetch_social_post("https://contoh.id/artikel")


class SocialAnalysisApiTests(APITestCase):
    def _post(self) -> SocialPost:
        return SocialPost(
            platform="x",
            url="https://x.com/akunx/status/123",
            canonical_url="https://x.com/akunx/status/123",
            text=SOCIAL_TEXT,
            title=SOCIAL_TEXT[:140],
            author="Akun X",
            publisher="X/Twitter · @akunx",
            published_at=datetime(2026, 10, 20, 10, tzinfo=UTC),
            meta={"platform": "x", "post_id": "123", "author_handle": "akunx"},
        )

    def test_social_url_creates_analysis_from_post(self) -> None:
        with patch(
            "intel.services.analysis_service.fetch_social_post", return_value=self._post()
        ) as fetch:
            response = self.client.post(
                "/api/v1/analyses",
                {"url": "https://x.com/akunx/status/123"},
                format="json",
            )

        self.assertEqual(response.status_code, 201, response.content)
        fetch.assert_called_once_with("https://x.com/akunx/status/123")
        payload = response.json()
        self.assertEqual(payload["content"]["source_type"], "social")
        self.assertEqual(payload["content"]["author"], "Akun X")
        self.assertEqual(payload["content"]["publisher"], "X/Twitter · @akunx")
        self.assertEqual(payload["content"]["url"], "https://x.com/akunx/status/123")
        self.assertEqual(payload["title"], SOCIAL_TEXT[:140])

    @override_settings(UNIFAPI_API_KEY="")
    def test_social_url_without_api_key_fails_without_network(self) -> None:
        response = self.client.post(
            "/api/v1/analyses",
            {"url": "https://www.tiktok.com/@akun/video/123"},
            format="json",
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("UNIFAPI_API_KEY", response.json()["detail"])

    def test_social_fetch_error_is_returned_as_detail(self) -> None:
        with patch(
            "intel.services.analysis_service.fetch_social_post",
            side_effect=SocialFetchError("Postingan tidak ditemukan."),
        ):
            response = self.client.post(
                "/api/v1/analyses",
                {"url": "https://www.instagram.com/p/DUajw4YkorV/"},
                format="json",
            )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"], "Postingan tidak ditemukan.")
