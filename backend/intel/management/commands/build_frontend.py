from django.core.management.base import BaseCommand, CommandError

from intel.services.frontend import FrontendBuildError, ensure_frontend_build


class Command(BaseCommand):
    help = "Build frontend React ke frontend/dist untuk disajikan Django."

    def handle(self, *args, **options):
        try:
            ensure_frontend_build(force=True)
        except FrontendBuildError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS("Frontend berhasil di-build."))
