from __future__ import annotations

from unittest import TestCase

from bs4 import BeautifulSoup

from intel.services.extraction import (
    ExtractionError,
    _ensure_public_url,
    _extract_links,
)

ARTICLE_HTML = """
<html><body>
  <a href="#top">Lompat ke isi</a>
  <a href="/">Halaman Utama</a>
  <nav><a href="/recent">Perubahan terbaru</a></nav>
  <p>
    Menurut <a href="https://example.org/laporan">laporan resmi lembaga</a>, data menunjukkan
    peningkatan. Lihat juga <a href="/artikel/terkait">artikel terkait kebijakan</a>.
  </p>
  <a href="mailto:redaksi@example.org">Email redaksi</a>
</body></html>
"""


class ExtractionTests(TestCase):
    def test_extract_links_prioritises_content_and_skips_navigation(self) -> None:
        soup = BeautifulSoup(ARTICLE_HTML, "html.parser")
        links = _extract_links(soup, "https://contoh.id/artikel")
        titles = [link["title"] for link in links]
        self.assertEqual(titles[0], "laporan resmi lembaga")
        self.assertNotIn("Halaman Utama", titles)
        self.assertNotIn("Lompat ke isi", titles)
        self.assertTrue(all(link["url"].startswith("https://") for link in links))
        self.assertNotIn("mailto", " ".join(link["url"] for link in links))

    def test_private_or_unsupported_hosts_are_blocked(self) -> None:
        for url in (
            "http://127.0.0.1/admin",
            "http://localhost:8000/",
            "http://10.0.0.5/internal",
            "file:///etc/passwd",
        ):
            with self.subTest(url=url):
                with self.assertRaises(ExtractionError):
                    _ensure_public_url(url)
