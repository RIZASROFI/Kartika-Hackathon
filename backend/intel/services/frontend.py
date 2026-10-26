"""Utilitas build frontend React untuk mode satu server."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from django.conf import settings


class FrontendBuildError(Exception):
    pass


def _run(command: list[str], cwd: Path) -> None:
    completed = subprocess.run(command, cwd=cwd)
    if completed.returncode != 0:
        raise FrontendBuildError(
            f"Perintah gagal: {' '.join(command)} (exit {completed.returncode})"
        )


def ensure_frontend_build(*, force: bool = False) -> bool:
    """Build `frontend/dist` bila belum ada. Kembalikan True bila build dijalankan."""
    dist_dir = settings.FRONTEND_DIST
    index_file = dist_dir / "index.html"
    if index_file.is_file() and not force:
        return False

    frontend_dir = dist_dir.parent
    if not (frontend_dir / "package.json").is_file():
        raise FrontendBuildError(f"Proyek frontend tidak ditemukan di {frontend_dir}")

    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if npm is None:
        raise FrontendBuildError(
            "npm tidak ditemukan. Instal Node.js, atau build manual dengan `npm run build`."
        )

    if not (frontend_dir / "node_modules").is_dir():
        _run([npm, "install", "--no-audit", "--no-fund"], frontend_dir)

    _run([npm, "run", "build"], frontend_dir)
    return True
