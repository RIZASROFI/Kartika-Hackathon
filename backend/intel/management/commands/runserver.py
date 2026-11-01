"""`manage.py runserver` dengan persiapan otomatis.

Menjalankan migrasi, membangun frontend bila `frontend/dist` belum ada, lalu
menyerahkan kendali ke runserver Django. Tidak ada pengisian data contoh:
database dibiarkan apa adanya agar analisis yang tampil hanya konten nyata.
"""

from django.contrib.staticfiles.management.commands.runserver import (
    Command as RunserverCommand,
)
from django.core.management import call_command

from intel.services.frontend import FrontendBuildError, ensure_frontend_build


class Command(RunserverCommand):
    help = "Siapkan database + frontend, lalu jalankan server pengembangan."

    def handle(self, *args, **options):
        call_command("migrate", interactive=False, verbosity=0)

        try:
            built = ensure_frontend_build()
        except FrontendBuildError as exc:
            self.stderr.write(self.style.WARNING(f"Build frontend gagal: {exc}"))
            self.stderr.write(
                "API tetap berjalan. Jalankan `npm run build` di folder frontend "
                "agar UI tersedia."
            )
        else:
            if built:
                self.stdout.write(self.style.SUCCESS("Frontend React selesai di-build."))

        super().handle(*args, **options)
