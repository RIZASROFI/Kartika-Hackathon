#!/usr/bin/env python
"""Utilitas baris perintah Django untuk KARTIKA Intel."""

import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "satria.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "Django tidak dapat diimpor. Pastikan virtualenv aktif dan dependensi "
            "sudah terpasang: pip install -r requirements.txt"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
