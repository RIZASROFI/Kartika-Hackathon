"""Penanganan error DRF dengan format yang dipakai frontend."""

from __future__ import annotations

from rest_framework.views import exception_handler


def _flatten(value) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for item in value.values():
            flattened = _flatten(item)
            if flattened:
                return flattened
        return None
    if isinstance(value, (list, tuple)):
        for item in value:
            flattened = _flatten(item)
            if flattened:
                return flattened
        return None
    return None


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None

    data = response.data
    if isinstance(data, dict) and set(data.keys()) == {"detail"}:
        return response

    message = _flatten(data) or "Permintaan gagal diproses."
    response.data = {"detail": message}
    return response
