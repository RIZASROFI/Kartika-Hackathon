"""Klien model bahasa dengan API kompatibel OpenAI.

Satu implementasi dipakai untuk Groq, Gemini, OpenRouter, maupun Ollama lokal;
pemilihan penyedia cukup lewat `LLM_BASE_URL` dan `LLM_MODEL`. Modul ini tidak
pernah menebak isi jawaban: keluaran wajib JSON valid dan divalidasi pemanggil.

Model reasoning kadang memakai token untuk berpikir sebelum menjawab, sehingga
balasan bisa terpotong (finish_reason=length). Karena itu permintaan diulang
sekali dengan anggaran token dua kali lipat sebelum dinyatakan gagal.
"""

from __future__ import annotations

import json
import logging

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 2


class LLMError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _extract_json(content: str) -> dict:
    cleaned = (content or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end <= start:
        raise LLMError("Model bahasa tidak mengembalikan objek JSON.")
    try:
        payload = json.loads(cleaned[start : end + 1])
    except ValueError as exc:
        raise LLMError("Balasan model bahasa bukan JSON yang valid.") from exc
    if not isinstance(payload, dict):
        raise LLMError("Balasan model bahasa bukan objek JSON.")
    return payload


def _request(body: dict) -> dict:
    """Kirim satu permintaan dan kembalikan payload JSON mentah."""
    try:
        with httpx.Client(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
            response = client.post(
                f"{settings.LLM_BASE_URL}/chat/completions",
                json=body,
                headers={
                    "Authorization": f"Bearer {settings.LLM_API_KEY}",
                    "Content-Type": "application/json",
                },
            )
    except httpx.HTTPError as exc:
        raise LLMError(
            f"Koneksi ke model bahasa gagal: {exc.__class__.__name__}."
        ) from exc

    if response.status_code in {401, 403}:
        raise LLMError(
            f"API key model bahasa ditolak (HTTP {response.status_code}).",
            status_code=response.status_code,
        )
    if response.status_code == 404:
        raise LLMError(
            "Model atau endpoint model bahasa tidak ditemukan (HTTP 404). "
            "Periksa LLM_MODEL dan LLM_BASE_URL.",
            status_code=404,
        )
    if response.status_code == 429:
        raise LLMError(
            "Kuota model bahasa habis (HTTP 429). Coba lagi nanti.",
            status_code=429,
        )
    if response.status_code >= 400:
        raise LLMError(
            f"Model bahasa mengembalikan HTTP {response.status_code}.",
            status_code=response.status_code,
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise LLMError("Respons model bahasa bukan JSON yang valid.") from exc
    if not isinstance(payload, dict):
        raise LLMError("Struktur respons model bahasa tidak dikenali.")
    return payload


def call_json(*, system: str, user: str) -> dict:
    """Kirim satu percakapan dan kembalikan objek JSON. Melempar LLMError saat gagal."""
    if not settings.LLM_ENABLED:
        raise LLMError("Integrasi model bahasa belum diaktifkan (LLM_ENABLED=false).")
    if not settings.LLM_API_KEY:
        raise LLMError("API key model bahasa (LLM_API_KEY) belum diatur.")
    if not settings.LLM_MODEL:
        raise LLMError("Nama model bahasa (LLM_MODEL) belum diatur.")

    budget = max(200, settings.LLM_MAX_TOKENS)
    for attempt in range(MAX_ATTEMPTS):
        payload = _request(
            {
                "model": settings.LLM_MODEL,
                "temperature": 0,
                "max_tokens": min(budget * (2**attempt), 8192),
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            }
        )

        try:
            choice = payload["choices"][0]
            content = choice["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("Struktur respons model bahasa tidak dikenali.") from exc

        if choice.get("finish_reason") == "length":
            if attempt + 1 < MAX_ATTEMPTS:
                logger.warning(
                    "llm_truncated_retry",
                    extra={"extra_fields": {"budget": budget * (2**attempt)}},
                )
                continue
            raise LLMError(
                "Balasan model terpotong karena batas token (finish_reason=length). "
                "Naikkan LLM_MAX_TOKENS atau kurangi jumlah klaim per analisis."
            )

        if not isinstance(content, str) or not content.strip():
            raise LLMError("Model bahasa mengembalikan jawaban kosong.")

        return _extract_json(content)

    raise LLMError(
        "Balasan model terpotong karena batas token (finish_reason=length)."
    )
