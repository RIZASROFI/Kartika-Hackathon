"""`manage.py runserver` dengan persiapan otomatis.

Menjalankan migrasi, mengisi data demo bila database kosong, membangun frontend
bila `frontend/dist` belum ada, lalu menyerahkan kendali ke runserver Django.
"""

from django.contrib.staticfiles.management.commands.runserver import (
    Command as RunserverCommand,
)
from django.core.management import call_command

from intel.services.frontend import FrontendBuildError, ensure_frontend_build
from intel.services.seed_service import seed_demo_data


class Command(RunserverCommand):
    help = (
        "Siapkan database + data demo + frontend, lalu jalankan server pengembangan."
    )

    def handle(self, *args, **options):
        call_command("migrate", interactive=False, verbosity=0)

        created = seed_demo_data()
        if created:
            self.stdout.write(
                self.style.SUCCESS(f"Seed demo: {created} analisis dimuat.")
            )

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
